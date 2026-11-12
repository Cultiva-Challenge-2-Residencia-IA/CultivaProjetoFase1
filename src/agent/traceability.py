"""Cálculo e persistência mínima dos metadados de rastreabilidade da resposta."""

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from uuid import uuid4

import yaml

from src.config import CORPUS_MANIFEST_PATH, CORPUS_RAG_DIR, TRACEABILITY_DB_PATH
from src.models.schemas import DocumentChunk, UsedPassage


def _digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical_digest(value: Any) -> str:
    return _digest(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode())


def corpus_fingerprint(
    chunks: Iterable[DocumentChunk],
    manifest_path: Path = CORPUS_MANIFEST_PATH,
    rag_dir: Path = CORPUS_RAG_DIR,
) -> str:
    """Hash do manifesto e dos JSONL das fontes que efetivamente alimentaram o índice."""
    chunks = list(chunks)
    source_ids = sorted({chunk.doc_id for chunk in chunks})
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    sources = [s for s in manifest["sources"] if s["id"] in source_ids]
    payload = {
        "manifest_version": manifest["version"],
        "sources": sources,
        "jsonl_sha256": {},
    }
    # O nome do JSONL não é necessariamente o id da fonte. Descobrir a associação
    # pelos próprios Trechos evita depender de convenções de nome de arquivo.
    source_paths: dict[str, Path] = {}
    for path in sorted(rag_dir.glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("fonte_id") in source_ids:
                source_paths[row["fonte_id"]] = path
    missing = set(source_ids) - source_paths.keys()
    if missing:
        raise ValueError(f"JSONL ausente para fontes indexadas: {', '.join(sorted(missing))}")
    payload["jsonl_sha256"] = {
        source_id: _digest(source_paths[source_id].read_bytes()) for source_id in sorted(source_ids)
    }
    return _canonical_digest(payload)


def passages_fingerprint(
    chunks: Iterable[DocumentChunk], manifest_path: Path = CORPUS_MANIFEST_PATH
) -> tuple[str, list[UsedPassage]]:
    chunks = list(chunks)
    source_ids = {chunk.doc_id for chunk in chunks}
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    refs = sorted(
        (source for source in manifest["sources"] if source["id"] in source_ids),
        key=lambda source: source["id"],
    )
    return _canonical_digest(refs), [
        UsedPassage(
            id=c.chunk_id,
            fonte_id=c.doc_id,
            pagina_pdf=c.pagina_pdf,
            link=c.fonte_url or (f"https://doi.org/{c.doi}" if c.doi else None),
            titulo=c.title,
        )
        for c in chunks
    ]


def new_response_id() -> str:
    return str(uuid4())


def save_response_trace(response: Any, db_path: Path = TRACEABILITY_DB_PATH) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """CREATE TABLE IF NOT EXISTS response_trace (
                response_id TEXT PRIMARY KEY, created_at TEXT NOT NULL, corpus_version TEXT NOT NULL,
                prompt_version TEXT NOT NULL, model_version TEXT NOT NULL, fontes_version TEXT NOT NULL,
                trechos_usados TEXT NOT NULL, feedback TEXT
            )"""
        )
        connection.execute(
            "INSERT OR REPLACE INTO response_trace VALUES (?, ?, ?, ?, ?, ?, ?, NULL)",
            (
                response.response_id,
                datetime.now(timezone.utc).isoformat(),
                response.corpus_version,
                response.prompt_version,
                response.model_version,
                response.fontes_version,
                json.dumps([item.model_dump() for item in response.trechos_usados], ensure_ascii=False),
            ),
        )


def register_incorrect_feedback(response_id: str, detail: str | None, db_path: Path = TRACEABILITY_DB_PATH) -> bool:
    if not db_path.exists():
        return False
    with sqlite3.connect(db_path) as connection:
        cursor = connection.execute(
            "UPDATE response_trace SET feedback = ? WHERE response_id = ?",
            (json.dumps({"tipo": "resposta_incorreta", "detalhe": detail}, ensure_ascii=False), response_id),
        )
        return cursor.rowcount == 1
