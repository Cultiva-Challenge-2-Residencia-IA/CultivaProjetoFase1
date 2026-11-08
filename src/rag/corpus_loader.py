"""Carregador do corpus para o índice (issues #4 e #7; contrato do ADR 0002).

Lê os Trechos de `corpus/nutricao/rag/*.jsonl`, aplica o gate de aprovação e converte cada
Trecho em `DocumentChunk` com `trecho_para_chunk`. A licença é só metadado e não filtra.
"""

import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterator, List

import yaml

from src.config import CORPUS_MANIFEST_PATH, CORPUS_RAG_DIR, INCLUDE_PENDING_SOURCES
from src.models.schemas import CuratedSourceRecord, DocumentChunk
from src.rag.contrato import trecho_para_chunk


def ler_trechos(rag_dir: Path = CORPUS_RAG_DIR) -> Iterator[Dict[str, Any]]:
    """Percorre todos os Trechos do corpus, na ordem dos arquivos."""
    for arquivo in sorted(rag_dir.glob("*.jsonl")):
        for linha in arquivo.read_text(encoding="utf-8").splitlines():
            if linha.strip():
                yield json.loads(linha)


def carregar_chunks_do_corpus(
    incluir_pendentes: bool = INCLUDE_PENDING_SOURCES,
    rag_dir: Path = CORPUS_RAG_DIR,
) -> List[DocumentChunk]:
    """Gate de aprovação: só fontes `aprovado`, ou também `pendente` com a flag de desenvolvimento."""
    aceitos = {"aprovado", "pendente"} if incluir_pendentes else {"aprovado"}
    chunks = [trecho_para_chunk(t) for t in ler_trechos(rag_dir) if t["approval_status"] in aceitos]
    if not chunks:
        raise ValueError(
            "Nenhum Trecho de fonte aprovada no corpus. Para desenvolvimento, use "
            "incluir_pendentes=True ou CULTIVA_INCLUIR_PENDENTES=true."
        )
    return chunks


def inventario_de_fontes(
    chunks: List[DocumentChunk], manifest_path: Path = CORPUS_MANIFEST_PATH
) -> List[CuratedSourceRecord]:
    """Uma linha por fonte indexada, com os dados do manifesto e a contagem de chunks."""
    manifesto = {
        s["id"]: s for s in yaml.safe_load(manifest_path.read_text(encoding="utf-8"))["sources"]
    }
    contagem = Counter(c.doc_id for c in chunks)
    primeiro: Dict[str, DocumentChunk] = {}
    for c in chunks:
        primeiro.setdefault(c.doc_id, c)
    inventario = []
    for fonte_id, n in contagem.items():
        c = primeiro[fonte_id]
        fonte = manifesto.get(fonte_id, {})
        inventario.append(
            CuratedSourceRecord(
                fonte_id=fonte_id,
                kind=fonte.get("kind", "pdf"),
                tipo_fonte=fonte.get("source_type", "desconhecido"),
                title=c.title,
                source_organization=c.source_organization,
                publication_year=c.publication_year,
                evidence_level=c.evidence_level,
                fonte_url=c.fonte_url,
                doi=c.doi,
                licenca=c.licenca or "pendente",
                approval_status=c.approval_status or "pendente",
                chunks_count=n,
            )
        )
    return sorted(inventario, key=lambda r: (r.kind, r.fonte_id))
