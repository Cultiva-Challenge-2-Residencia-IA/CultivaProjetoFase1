"""Banco vetorial (ChromaDB), embeddings e base curada da entrega."""

import numpy as np

from src.rag.corpus_loader import carregar_chunks_do_corpus, inventario_de_fontes
from src.retrieval.hybrid_retriever import HybridRetriever
from src.retrieval.vector_store import DenseMultilingualEmbedder, NutritionVectorStore


def test_base_curada_tem_ao_menos_20_documentos_fonte() -> None:
    inventario = inventario_de_fontes(carregar_chunks_do_corpus(incluir_pendentes=True))
    assert len(inventario) >= 20
    assert all(f.kind == "pdf" for f in inventario)
    assert len(inventario) == 22
    assert all(f.chunks_count > 0 for f in inventario)


def test_gate_de_aprovacao_so_deixa_passar_fontes_aprovadas() -> None:
    aprovados = carregar_chunks_do_corpus(incluir_pendentes=False)
    assert aprovados
    assert {c.approval_status for c in aprovados} == {"aprovado"}
    todos = carregar_chunks_do_corpus(incluir_pendentes=True)
    assert len(todos) > len(aprovados)


def test_embedder_multilingue_gera_vetores_normalizados_de_384d() -> None:
    embedder = DenseMultilingualEmbedder()
    vecs = embedder.embed_documents(
        [
            "A fibra solúvel beta-glucana da aveia reduz o colesterol LDL sérico.",
            "Oat beta-glucan soluble fiber reduces serum LDL cholesterol.",
        ]
    )
    assert len(vecs) == 2 and len(vecs[0]) == 384
    v0, v1 = np.array(vecs[0]), np.array(vecs[1])
    assert np.isclose(np.linalg.norm(v0), 1.0, atol=1e-4)
    assert np.isclose(np.linalg.norm(v1), 1.0, atol=1e-4)
    # Alinhamento semântico entre português e inglês
    assert float(np.dot(v0, v1)) > 0.65


def test_chromadb_persiste_e_guarda_metadados_de_rastreabilidade(tmp_path) -> None:
    amostra = carregar_chunks_do_corpus(incluir_pendentes=True)[:12]
    vstore = NutritionVectorStore(
        chunks=amostra,
        persist_directory=tmp_path / "test_chroma",
        collection_name="test_nutricao",
        use_persistent=True,
    )
    stats = vstore.get_stats()
    assert stats["total_vectors_indexed"] == 12
    assert stats["embedding_dimension"] == 384
    assert "ChromaDB" in stats["vector_db_engine"]
    assert stats["collection_name"].startswith("test_nutricao_")

    meta = vstore.collection.get(ids=[amostra[0].chunk_id], include=["metadatas"])["metadatas"][0]
    assert meta["fonte_id"] == amostra[0].doc_id
    assert meta["approval_status"] in {"pendente", "aprovado"}

    hits = vstore.similarity_search("ultraprocessados e obesidade", top_k=3)
    assert len(hits) == 3
    idx, sim = hits[0]
    assert 0 <= idx < 12 and 0.0 <= sim <= 1.0


def test_busca_hibrida_com_banco_vetorial_recupera_a_fonte_certa(tmp_path) -> None:
    chunks = [
        c
        for c in carregar_chunks_do_corpus(incluir_pendentes=True)
        if c.doc_id in {"souza-backes-universitarios-csc-2020", "martins-ultraprocessados-rsp-2013"}
    ]
    retriever = HybridRetriever(chunks)
    resultados = retriever.retrieve(
        "Autopercepção do consumo alimentar e adesão aos Dez Passos entre universitários",
        top_k=4,
    )
    assert "souza-backes-universitarios-csc-2020" in {r.chunk.doc_id for r in resultados}
