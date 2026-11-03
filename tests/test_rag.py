from rag.chunking import carregar_trechos
from rag.retriever import BuscaPorPalavras
from rag.verificador import citacoes_validas, extrair_citacoes, remover_citacoes


def test_fixture_tem_trechos_com_ids_unicos():
    trechos = carregar_trechos()
    ids = [t.id for t in trechos]
    assert len(ids) >= 10
    assert len(ids) == len(set(ids))
    assert all(t.fonte_id == "guia-alimentar-2014" and t.pagina_pdf > 0 for t in trechos)


def test_busca_encontra_trecho_relevante():
    busca = BuscaPorPalavras(carregar_trechos())
    ids = [t.id for t in busca.buscar("Por que evitar alimentos ultraprocessados?")]
    assert "guia-2014-p051-a" in ids or "guia-2014-p051-b" in ids


def test_busca_sem_termo_do_corpus_volta_vazia():
    busca = BuscaPorPalavras(carregar_trechos())
    assert busca.buscar("jejum intermitente") == []


def test_citacoes():
    texto = "Prefira comida feita na hora [guia-2014-p051-b] e varie [guia-2014-p126-a]."
    assert extrair_citacoes(texto) == ["guia-2014-p051-b", "guia-2014-p126-a"]
    ids = {"guia-2014-p051-b", "guia-2014-p126-a"}
    assert citacoes_validas(texto, ids) == ["guia-2014-p051-b", "guia-2014-p126-a"]
    assert remover_citacoes(texto) == "Prefira comida feita na hora e varie."


def test_citacao_inventada_invalida_a_resposta():
    texto = "Algo [guia-2014-p051-b] e algo inventado [fonte-que-nao-existe]."
    assert citacoes_validas(texto, {"guia-2014-p051-b"}) == []
