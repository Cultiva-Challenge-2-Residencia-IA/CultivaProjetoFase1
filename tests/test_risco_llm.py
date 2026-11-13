"""Camada semântica do detector de risco (issue #48), sem Ollama: classificador simulado e HTTP falso."""

from unittest.mock import MagicMock

import httpx
import pytest

from src.agent.consultant_baseline import NutritionConsultantBaseline
from src.guardrails.risco import MENSAGEM_ACOLHIMENTO
from src.guardrails.risco.classificador_llm import ClassificadorRiscoLLM, ResultadoLLM


def _consultor(risco_llm):
    consultor = NutritionConsultantBaseline.__new__(NutritionConsultantBaseline)
    consultor.risco_llm = risco_llm
    consultor._consultar_sem_risco = MagicMock(
        side_effect=lambda q, k: NutritionConsultantBaseline._resposta_fixa(
            consultor, q, "resposta normal", guardrail_triggered=False, intent_category="GENERAL"))
    return consultor


def _llm(resultado):
    llm = MagicMock()
    llm.classificar.return_value = resultado
    return llm


def test_lexico_aciona_sem_consultar_o_llm():
    llm = _llm(ResultadoLLM(False, [], 0.1))
    resposta = _consultor(llm).consult("quero me matar")
    assert resposta.risk_triggered and resposta.risk_layer == "lexico"
    llm.classificar.assert_not_called()


def test_llm_acrescenta_deteccao_quando_o_lexico_nao_aciona():
    llm = _llm(ResultadoLLM(True, ["ideacao_suicida"], 0.3))
    consultor = _consultor(llm)
    resposta = consultor.consult("uma frase que nenhuma regra prevê")
    assert resposta.risk_triggered and resposta.risk_layer == "llm"
    assert resposta.evidence_summary == MENSAGEM_ACOLHIMENTO
    assert resposta.risk_categories == ["ideacao_suicida"]
    consultor._consultar_sem_risco.assert_not_called()


def test_llm_sem_risco_segue_o_fluxo_normal():
    resposta = _consultor(_llm(ResultadoLLM(False, [], 0.2))).consult("Quais frutas têm vitamina C?")
    assert not resposta.risk_triggered and resposta.risk_llm_status == "ok"


def test_falha_do_llm_vale_so_o_lexico_e_fica_registrada():
    resposta = _consultor(_llm(None)).consult("Quais frutas têm vitamina C?")
    assert not resposta.risk_triggered and resposta.risk_llm_status == "falhou"


def test_sem_camada_llm_o_status_fica_vazio():
    resposta = _consultor(None).consult("Quais frutas têm vitamina C?")
    assert resposta.risk_llm_status is None


class _Http:
    """Substitui httpx.Client: devolve o conteúdo dado ou levanta a exceção dada."""

    def __init__(self, conteudo=None, erro=None):
        self.conteudo, self.erro = conteudo, erro

    def __call__(self, timeout):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def post(self, url, json):
        if self.erro:
            raise self.erro
        resposta = MagicMock()
        resposta.json.return_value = {"message": {"content": self.conteudo}}
        return resposta


@pytest.mark.parametrize(("modelo", "conteudo", "risco", "categorias"), [
    ("llama-guard3:1b", "safe", False, []),
    ("llama-guard3:1b", "unsafe\nS11", True, ["autolesao_ou_suicidio"]),
    ("llama-guard3:1b", "unsafe\nS2", False, []),
    ("qwen2.5:7b", '{"nivel": 7, "categoria": "autolesao"}', True, ["autolesao"]),
    ("qwen2.5:7b", '{"nivel": 0, "categoria": null}', False, []),
    ("qwen2.5:7b", '{"nivel": 3, "categoria": "outra"}', True, ["risco_nao_categorizado"]),
])
def test_interpreta_a_saida_dos_modelos(monkeypatch, modelo, conteudo, risco, categorias):
    monkeypatch.setattr(httpx, "Client", _Http(conteudo))
    resultado = ClassificadorRiscoLLM(modelo, limiar=1).classificar("texto")
    assert resultado.risco is risco and resultado.categorias == categorias


@pytest.mark.parametrize(("nivel", "limiar", "risco"), [(0, 1, False), (1, 1, True), (4, 5, False), (5, 5, True)])
def test_limiar_do_nivel_de_preocupacao(monkeypatch, nivel, limiar, risco):
    monkeypatch.setattr(httpx, "Client", _Http(f'{{"nivel": {nivel}, "categoria": "ideacao_suicida"}}'))
    resultado = ClassificadorRiscoLLM("qwen2.5:7b", limiar=limiar).classificar("texto")
    assert resultado.risco is risco and resultado.nivel == nivel


@pytest.mark.parametrize(("conteudo", "erro"), [
    (None, httpx.ConnectError("Ollama fora")),
    (None, httpx.ReadTimeout("tempo limite")),
    ("resposta sem json", None),
    ('{"categoria": "autolesao"}', None),
    ('{"nivel": 11, "categoria": "autolesao"}', None),
    ('{"nivel": true, "categoria": "autolesao"}', None),
])
def test_falha_ou_saida_invalida_devolve_none(monkeypatch, conteudo, erro):
    monkeypatch.setattr(httpx, "Client", _Http(conteudo, erro))
    assert ClassificadorRiscoLLM("qwen2.5:7b").classificar("texto") is None
