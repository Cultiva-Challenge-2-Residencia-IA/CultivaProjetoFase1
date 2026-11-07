import numpy as np

from src.ingestion.contextual_chunker import ContextualChunker
from src.retrieval.hybrid_retriever import HybridRetriever
from src.retrieval.vector_store import DenseMultilingualEmbedder, NutritionVectorStore


def test_curated_knowledge_base_exceeds_minimum_20_source_documents() -> None:
    chunker = ContextualChunker()
    chunks = chunker.load_and_chunk_directory()
    inventory = chunker.get_curated_sources_inventory(chunks)

    assert len(inventory) >= 20
    pdf_sources = [s for s in inventory if s.source_type == "PDF_OFICIAL_CORPUS"]
    pubmed_sources = [s for s in inventory if s.source_type == "PUBMED_PEER_REVIEWED"]

    assert len(pdf_sources) == 6
    assert len(pubmed_sources) >= 20
    assert (len(pdf_sources) + len(pubmed_sources)) >= 35


def test_dense_multilingual_embedder_produces_normalized_384d_vectors() -> None:
    embedder = DenseMultilingualEmbedder()
    vecs = embedder.embed_documents(
        [
            "A fibra solúvel beta-glucana da aveia reduz o colesterol LDL sérico.",
            "Oat beta-glucan soluble fiber reduces serum LDL cholesterol.",
        ]
    )
    assert len(vecs) == 2
    assert len(vecs[0]) == 384

    v0 = np.array(vecs[0])
    v1 = np.array(vecs[1])
    assert np.isclose(np.linalg.norm(v0), 1.0, atol=1e-4)
    assert np.isclose(np.linalg.norm(v1), 1.0, atol=1e-4)
    # Verifica alinhamento semântico cross-lingual PT-BR <-> EN
    cosine_sim = float(np.dot(v0, v1))
    assert cosine_sim > 0.65


def test_chromadb_vector_store_persists_and_filters_by_metadata(tmp_path) -> None:
    chunker = ContextualChunker()
    all_chunks = chunker.load_and_chunk_directory()
    sample_chunks = all_chunks[:12]

    vstore = NutritionVectorStore(
        chunks=sample_chunks,
        persist_directory=tmp_path / "test_chroma",
        collection_name="test_nutricao_collection",
        use_persistent=True,
    )
    stats = vstore.get_stats()
    assert stats["total_vectors_indexed"] == 12
    assert stats["embedding_dimension"] == 384
    assert "ChromaDB" in stats["vector_db_engine"]

    hits = vstore.similarity_search(
        "Políticas públicas e direito à alimentação adequada no Guia Alimentar",
        top_k=3,
    )
    assert len(hits) == 3
    top_idx, top_sim = hits[0]
    assert 0 <= top_idx < 12
    assert 0.0 <= top_sim <= 1.0


def test_hybrid_retriever_queries_curated_corpus_pdfs_from_manifest() -> None:
    chunker = ContextualChunker()
    chunks = chunker.load_and_chunk_directory()
    retriever = HybridRetriever(chunks)

    results = retriever.retrieve(
        "Autopercepção do consumo alimentar e adesão aos Dez Passos entre universitários de Porto Alegre",
        top_k=4,
    )
    retrieved_sources = {r.chunk.source_id for r in results}
    assert "souza-backes-universitarios-csc-2020" in retrieved_sources
