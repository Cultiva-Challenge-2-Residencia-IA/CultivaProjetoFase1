"""Banco vetorial (ChromaDB), embeddings e base curada da entrega."""

import json

import numpy as np
import pytest

from src.config import BENCHMARK_QUESTIONS_PATH, EMBEDDING_MODEL_NAME
from src.rag.corpus_loader import carregar_chunks_do_corpus, inventario_de_fontes
from src.retrieval.hybrid_retriever import HybridRetriever
from src.retrieval.vector_store import DenseMultilingualEmbedder, NutritionVectorStore, dimensao_do_modelo


def test_base_curada_tem_ao_menos_20_documentos_fonte() -> None:
    inventario = inventario_de_fontes(carregar_chunks_do_corpus(incluir_pendentes=True))
    assert len(inventario) >= 20
    assert all(f.kind == "pdf" for f in inventario)
    assert len(inventario) == 31
    assert all(f.chunks_count > 0 for f in inventario)


def test_gate_de_aprovacao_so_deixa_passar_fontes_aprovadas() -> None:
    aprovados = carregar_chunks_do_corpus(incluir_pendentes=False)
    assert aprovados
    assert {c.approval_status for c in aprovados} == {"aprovado"}
    todos = carregar_chunks_do_corpus(incluir_pendentes=True)
    assert len(todos) > len(aprovados)


def test_embedder_multilingue_gera_vetores_normalizados_na_dimensao_do_modelo() -> None:
    embedder = DenseMultilingualEmbedder()
    vecs = embedder.embed_documents(
        [
            "A fibra solúvel beta-glucana da aveia reduz o colesterol LDL sérico.",
            "Oat beta-glucan soluble fiber reduces serum LDL cholesterol.",
        ]
    )
    assert len(vecs) == 2 and len(vecs[0]) == embedder.dimension == dimensao_do_modelo(EMBEDDING_MODEL_NAME)
    v0, v1 = np.array(vecs[0]), np.array(vecs[1])
    assert np.isclose(np.linalg.norm(v0), 1.0, atol=1e-4)
    assert np.isclose(np.linalg.norm(v1), 1.0, atol=1e-4)


@pytest.mark.embeddings_reais
def test_embedder_alinha_portugues_e_ingles() -> None:
    embedder = DenseMultilingualEmbedder()
    v0, v1 = (np.array(v) for v in embedder.embed_documents([
        "A fibra solúvel beta-glucana da aveia reduz o colesterol LDL sérico.",
        "Oat beta-glucan soluble fiber reduces serum LDL cholesterol.",
    ]))
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
    assert stats["embedding_dimension"] == dimensao_do_modelo(EMBEDDING_MODEL_NAME)
    assert "ChromaDB" in stats["vector_db_engine"]
    assert stats["collection_name"].startswith("test_nutricao_")

    meta = vstore.collection.get(ids=[amostra[0].chunk_id], include=["metadatas"])["metadatas"][0]
    assert meta["fonte_id"] == amostra[0].doc_id
    assert meta["approval_status"] in {"pendente", "aprovado"}

    hits = vstore.similarity_search("ultraprocessados e obesidade", top_k=3)
    assert len(hits) == 3
    idx, sim = hits[0]
    assert 0 <= idx < 12 and 0.0 <= sim <= 1.0


def test_cache_grava_por_lote_e_guarda_o_que_ja_foi_calculado(tmp_path, monkeypatch) -> None:
    """Uma indexação interrompida no meio mantém no cache os lotes já calculados."""
    from src.retrieval.vector_store import CacheDeVetores

    embedder = DenseMultilingualEmbedder()
    monkeypatch.setattr(embedder, "LOTE_DO_CACHE", 2)
    original, chamadas = embedder._vetores, []

    def vetores_que_falham_no_terceiro_lote(textos):
        chamadas.append(len(textos))
        if len(chamadas) == 3:
            raise KeyboardInterrupt
        return original(textos)

    monkeypatch.setattr(embedder, "_vetores", vetores_que_falham_no_terceiro_lote)
    cache = CacheDeVetores(tmp_path / "vetores.sqlite3")
    textos = [f"texto {i} sobre fibra e aveia" for i in range(6)]
    with pytest.raises(KeyboardInterrupt):
        embedder.embed_documents(textos, cache=cache)
    chaves = [CacheDeVetores.chave(embedder.model_name, t) for t in textos]
    assert len(cache.buscar(chaves)) == 4


def test_cache_de_vetores_so_calcula_trechos_novos(tmp_path) -> None:
    """Uma segunda coleção com os mesmos Trechos reaproveita os vetores, com os mesmos valores."""
    amostra = carregar_chunks_do_corpus(incluir_pendentes=True)[:8]
    cache = tmp_path / "vetores.sqlite3"
    primeira = NutritionVectorStore(chunks=amostra[:6], collection_name="cache_a", use_persistent=False,
                                    cache_vetores=cache)
    assert primeira.embedder.calculados == 6
    segunda = NutritionVectorStore(chunks=amostra, collection_name="cache_b", use_persistent=False,
                                   cache_vetores=cache)
    assert segunda.embedder.calculados == 2
    ids = [c.chunk_id for c in amostra[:6]]
    a = primeira.collection.get(ids=ids, include=["embeddings"])["embeddings"]
    b = segunda.collection.get(ids=ids, include=["embeddings"])["embeddings"]
    assert np.allclose(np.asarray(a), np.asarray(b), atol=1e-6)


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



@pytest.mark.embeddings_reais
def test_hnsw_recupera_os_mesmos_vizinhos_da_busca_exata_e_e_estavel(tmp_path) -> None:
    """O HNSW é aproximado: com `ef_search` adequado, o top-24 deve coincidir com a busca
    exata e não variar ao recarregar o índice persistido (requisito do gate de determinismo)."""
    chunks = carregar_chunks_do_corpus()
    kwargs = dict(
        chunks=chunks,
        persist_directory=tmp_path / "chroma_hnsw",
        collection_name="test_hnsw",
        use_persistent=True,
    )
    consultas = [
        q["query"]
        for q in json.loads(BENCHMARK_QUESTIONS_PATH.read_text(encoding="utf-8"))
    ]
    construida = NutritionVectorStore(**kwargs)
    recarregada = NutritionVectorStore(**kwargs)

    ids = [c.chunk_id for c in chunks]
    res = construida.collection.get(ids=ids, include=["embeddings"])
    por_id = dict(zip(res["ids"], res["embeddings"]))
    matriz = np.asarray([por_id[i] for i in ids])

    acertos = 0
    for consulta in consultas:
        hnsw = construida.similarity_search(consulta, top_k=24)
        assert recarregada.similarity_search(consulta, top_k=24) == hnsw
        q = np.asarray(construida.embedder.embed_query(consulta))
        exatos = set(np.argsort(-(matriz @ q))[:24].tolist())
        acertos += len(exatos & {i for i, _ in hnsw})
    assert acertos / (24 * len(consultas)) >= 0.99
