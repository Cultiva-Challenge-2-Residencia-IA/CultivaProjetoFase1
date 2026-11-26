"""Issue #121: o reranker é carregado na criação do serviço, e não na primeira pergunta."""

from src.chat.fabrica import pre_carregar_rerankers
from src.retrieval import reranker_cruzado
from src.retrieval.reranker_cruzado import RerankerCruzado


class AgenteFalso:
    def __init__(self, reranker=None):
        self.reranker_cruzado = reranker


def test_carregar_carrega_o_modelo_uma_vez(monkeypatch):
    carregados = []
    monkeypatch.setattr(reranker_cruzado, "_modelo", lambda nome: carregados.append(nome))
    RerankerCruzado("modelo-falso").carregar()
    assert carregados == ["modelo-falso"]


def test_pre_carga_so_dos_agentes_com_reranker(monkeypatch):
    carregados = []
    monkeypatch.setattr(reranker_cruzado, "_modelo", lambda nome: carregados.append(nome))
    reranker = RerankerCruzado("modelo-falso")
    pre_carregar_rerankers([AgenteFalso(reranker), AgenteFalso(None), AgenteFalso(reranker)])
    assert carregados == ["modelo-falso"]  # o mesmo objeto não é carregado duas vezes


def test_sem_reranker_em_nenhuma_area_nada_e_carregado(monkeypatch):
    carregados = []
    monkeypatch.setattr(reranker_cruzado, "_modelo", lambda nome: carregados.append(nome))
    pre_carregar_rerankers([AgenteFalso(None), AgenteFalso(None)])
    assert carregados == []
