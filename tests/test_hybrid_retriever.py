from collections import Counter

from src.config import GUIDELINES_DIR, GUIDELINES_PATH
from src.ingestion.contextual_chunker import ContextualChunker
from src.retrieval.hybrid_retriever import HybridRetriever


def test_contextual_chunker_creates_enriched_headers_from_official_guia_alimentar() -> None:
    chunker = ContextualChunker()
    chunks = chunker.load_and_chunk_json(GUIDELINES_PATH)

    assert len(chunks) >= 180
    first = chunks[0]
    assert "[Documento:" in first.contextualized_text
    assert "Ministério da Saúde" in first.contextualized_text
    assert first.evidence_level == "GUIDELINE_CONSENSUS"


def test_multi_document_directory_loader_includes_guia_and_pubmed() -> None:
    chunker = ContextualChunker()
    chunks = chunker.load_and_chunk_directory(GUIDELINES_DIR)

    doc_ids = {c.doc_id for c in chunks}
    assert len(chunks) >= 220
    assert "GUIA_MS_CAP2_ESCOLHA_ALIMENTOS" in doc_ids
    assert "PUBMED_FIBER_MICROBIOTA" in doc_ids
    assert "DOC_GLICEMIA_CARBOIDRATOS_03" in doc_ids


def test_hybrid_retriever_enforces_document_diversification_in_top_k() -> None:
    chunker = ContextualChunker()
    chunks = chunker.load_and_chunk_directory(GUIDELINES_DIR)
    retriever = HybridRetriever(chunks)

    results = retriever.retrieve(
        "Quais são as quatro categorias de alimentos definidas pelo Guia Alimentar e qual é a regra de ouro?",
        top_k=4,
        max_chunks_per_doc=2,
    )
    assert len(results) == 4
    counts = Counter(r.chunk.doc_id for r in results)
    assert max(counts.values()) <= 2
    assert len(counts) >= 2


def test_hybrid_retriever_finds_comensalidade_chapter() -> None:
    chunker = ContextualChunker()
    chunks = chunker.load_and_chunk_directory(GUIDELINES_DIR)
    retriever = HybridRetriever(chunks)

    results = retriever.retrieve(
        "Quais são as orientações sobre o ato de comer, comensalidade, comer com atenção e em companhia?",
        top_k=4,
    )
    top_doc_ids = [r.chunk.doc_id for r in results]
    assert results[0].chunk.doc_id == "GUIA_MS_CAP4_COMENSALIDADE"
    assert results[0].rrf_score > 0
    assert results[0].rerank_score >= results[0].rrf_score
    assert "GUIA_MS_CAP4_COMENSALIDADE" in top_doc_ids
