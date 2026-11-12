import json
from types import SimpleNamespace

from src.agent.traceability import (
    corpus_fingerprint,
    register_incorrect_feedback,
    save_response_trace,
)
from src.models.schemas import DocumentChunk, UsedPassage


def _chunk() -> DocumentChunk:
    return DocumentChunk(
        chunk_id="fonte-p001-01",
        doc_id="fonte",
        title="Documento de teste",
        source_organization="Instituição",
        publication_year=2026,
        clinical_domain="nutricao",
        evidence_level="GRADE_B",
        section_path="Resumo (pág. 1)",
        raw_text="Texto",
        contextualized_text="Texto",
        pagina_pdf=1,
        fonte_url="https://example.org/fonte",
        approval_status="aprovado",
    )


def test_corpus_fingerprint_tracks_manifest_and_jsonl(tmp_path) -> None:
    manifest = tmp_path / "manifest.yaml"
    rag = tmp_path / "rag"
    rag.mkdir()
    manifest.write_text(
        'version: 1\nsources:\n  - id: fonte\n    version: "2026"\n    approval_status: aprovado\n',
        encoding="utf-8",
    )
    jsonl = rag / "fonte.jsonl"
    jsonl.write_text(json.dumps({"fonte_id": "fonte", "id": "fonte-p001-01"}) + "\n", encoding="utf-8")

    original = corpus_fingerprint([_chunk()], manifest, rag)
    assert original == corpus_fingerprint([_chunk()], manifest, rag)
    jsonl.write_text(json.dumps({"fonte_id": "fonte", "id": "fonte-p001-02"}) + "\n", encoding="utf-8")
    assert corpus_fingerprint([_chunk()], manifest, rag) != original


def test_response_trace_can_be_linked_to_incorrect_feedback(tmp_path) -> None:
    db_path = tmp_path / "trace.sqlite3"
    response = SimpleNamespace(
        response_id="response-123",
        corpus_version="corpus-hash",
        prompt_version="prompt-hash",
        model_version="provider:model",
        fontes_version="sources-hash",
        trechos_usados=[
            UsedPassage(id="fonte-p001-01", fonte_id="fonte", pagina_pdf=1, titulo="Documento")
        ],
    )

    save_response_trace(response, db_path)
    assert register_incorrect_feedback("response-123", "Citação não sustenta a frase", db_path)
    assert not register_incorrect_feedback("nao-existe", None, db_path)
