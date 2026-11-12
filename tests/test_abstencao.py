"""Resposta "não sei" sem evidência no corpus (RF-IA01, issue #6)."""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.agent.consultant_baseline import NutritionConsultantBaseline
from src.agent.guardrails import LegalGuardrail
from src.config import ABSTENCAO_LIMIAR_COSSENO
from src.evaluation.gate import FALHOU, PASSOU, PENDENTE, avaliar
from src.models.schemas import CausalGraphPath
from src.rag.abstencao import MENSAGEM_NAO_SEI, sem_evidencia

RAIZ = Path(__file__).resolve().parents[1]


def _consultor(similaridade, caminhos_grafo=()):
    """Consultor com busca, TACO, grafo e LLM substituídos por mocks, com a similaridade fixada."""
    consultor = NutritionConsultantBaseline.__new__(NutritionConsultantBaseline)
    consultor.guardrail = LegalGuardrail()
    consultor.retriever = MagicMock()
    consultor.retriever.retrieve.return_value = []
    consultor.retriever.similaridade_maxima.return_value = similaridade
    consultor.taco_tool = MagicMock()
    consultor.taco_tool.auto_query_from_question.return_value = ([], "")
    consultor.graph_engine = MagicMock()
    consultor.graph_engine.traverse_for_query.return_value = (list(caminhos_grafo), "contexto do grafo" if caminhos_grafo else "")
    consultor.llm_client = MagicMock()
    consultor.llm_client.generate_structured_synthesis.return_value = (
        {"evidence_summary": "síntese", "physiological_mechanism": "", "protocol_findings": "",
         "food_sources_or_compounds": [], "evidence_grade": "N/A"}, "local_extractive_synthesis")
    return consultor


def _caminho():
    return CausalGraphPath(
        path_id="PATH_X", food_node="Cúrcuma", compound_node="Curcumina", mechanism_node="m",
        outcome_node="o", effect_direction="MODULATES", relationship_nature="CLINICAL_GUIDELINE_CONSENSUS",
        evidence_grade="GRADE_B", studied_protocol="p", source_reference="r")


def test_limiar():
    assert sem_evidencia(ABSTENCAO_LIMIAR_COSSENO - 0.01, ABSTENCAO_LIMIAR_COSSENO)
    assert not sem_evidencia(ABSTENCAO_LIMIAR_COSSENO, ABSTENCAO_LIMIAR_COSSENO)


def test_sem_evidencia_responde_nao_sei_sem_chamar_o_llm():
    consultor = _consultor(similaridade=0.10)
    resposta = consultor.consult("Como eu troco o pneu do carro?")
    assert resposta.abstencao is True
    assert resposta.evidence_summary == MENSAGEM_NAO_SEI
    assert resposta.retrieval_mode == "ABSTENTION_FIXED_MESSAGE"
    assert resposta.similaridade_maxima == 0.10
    assert resposta.citations == [] and resposta.retrieved_chunks == []
    consultor.llm_client.generate_structured_synthesis.assert_not_called()


def test_com_evidencia_segue_o_fluxo_normal():
    consultor = _consultor(similaridade=0.80)
    resposta = consultor.consult("Vegetariano precisa suplementar vitamina B12?")
    assert resposta.abstencao is False
    assert resposta.similaridade_maxima == 0.80
    consultor.llm_client.generate_structured_synthesis.assert_called_once()


def test_sem_trecho_mas_com_grafo_responde_so_com_o_grafo():
    """Decisão de 12/11/2026: grafo ou TACO com resultado respondem mesmo sem Trecho no limiar."""
    consultor = _consultor(similaridade=0.10, caminhos_grafo=[_caminho()])
    resposta = consultor.consult("Cúrcuma com pimenta-do-reino é melhor absorvida?")
    assert resposta.abstencao is False
    argumentos = consultor.llm_client.generate_structured_synthesis.call_args.kwargs
    assert argumentos["retrieved_chunks"] == []
    assert argumentos["graph_context_str"] == "contexto do grafo"


def test_mensagem_nao_sei_e_fixa_e_orienta():
    assert "fontes aprovadas" in MENSAGEM_NAO_SEI and "nutricionista" in MENSAGEM_NAO_SEI


def test_conjunto_de_abstencao_esta_bem_formado():
    dados = json.loads((RAIZ / "eval/abstencao/casos.json").read_text(encoding="utf-8"))
    casos = dados["casos"]
    assert len({c["id"] for c in casos}) == len(casos)
    tipos = {c["tipo"] for c in casos}
    assert {"dentro", "nutricao_fora_do_corpus", "fora_de_nutricao"} <= tipos
    assert {c["split"] for c in casos} == {"dev", "test"}
    assert all(c["esperado"] == ("responder" if c["tipo"] in ("dentro", "grafo_sem_corpus") else "nao_sei") for c in casos)


@pytest.mark.parametrize("metricas, esperado", [
    ({"nao_sei_fora_de_nutricao": 0.95, "respostas_esperadas": 1.0}, {PASSOU}),
    ({"nao_sei_fora_de_nutricao": 0.50, "respostas_esperadas": 1.0}, {PASSOU, FALHOU}),
])
def test_gate_de_abstencao(metricas, esperado):
    config = {"abstencao": {"nao_sei_fora_de_nutricao": 0.90, "respostas_esperadas": 0.95}}
    relatorio = {"overall_metrics": {}, "abstention_metrics": metricas}
    status = {r.status for r in avaliar(relatorio, {"overall_metrics": {}}, config)}
    assert status == esperado


def test_gate_de_abstencao_sem_metricas_fica_pendente():
    resultados = avaliar({"overall_metrics": {}}, {"overall_metrics": {}}, {"abstencao": {"respostas_esperadas": 0.95}})
    assert [r.status for r in resultados] == [PENDENTE]
