"""Resposta "não sei" sem evidência no corpus (RF-IA01, issue #6)."""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.agent.consultant_baseline import NutritionConsultantBaseline
from src.agent.guardrails import LegalGuardrail
from src.config import ABSTENCAO_LIMIAR_COSSENO
from src.evaluation.gate import FALHOU, PASSOU, PENDENTE, avaliar
from src.models.schemas import CausalGraphPath, DocumentChunk, RetrievedChunk
from src.rag.abstencao import MENSAGEM_NAO_SEI, fora_do_dominio, tem_termo_de_nutricao

RAIZ = Path(__file__).resolve().parents[1]


def _consultor(similaridade, caminhos_grafo=()):
    """Consultor com busca, TACO, grafo e LLM substituídos por mocks, com a similaridade fixada."""
    consultor = NutritionConsultantBaseline.__new__(NutritionConsultantBaseline)
    consultor.guardrail = LegalGuardrail()
    consultor.corpus_version = "corpus-teste"
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


def _trecho():
    return RetrievedChunk(chunk=DocumentChunk(
        chunk_id="azevedo-jejum-intermitente-ramb-2013-p002-01", doc_id="azevedo-jejum-intermitente-ramb-2013",
        title="Jejum intermitente", source_organization="RAMB", publication_year=2013, clinical_domain="nutricao",
        evidence_level="GRADE_B", section_path="Resumo", raw_text="melhor adesão ao jejum intermitente",
        contextualized_text=""))


def _caminho():
    return CausalGraphPath(
        path_id="PATH_X", food_node="Cúrcuma", compound_node="Curcumina", mechanism_node="m",
        outcome_node="o", effect_direction="MODULATES", relationship_nature="CLINICAL_GUIDELINE_CONSENSUS",
        evidence_grade="GRADE_B", studied_protocol="p", source_reference="r")


def test_fora_do_dominio_exige_os_dois_sinais():
    baixo, alto = ABSTENCAO_LIMIAR_COSSENO - 0.1, ABSTENCAO_LIMIAR_COSSENO + 0.1
    assert fora_do_dominio("Como faço para tirar o passaporte?", baixo, ABSTENCAO_LIMIAR_COSSENO)
    assert not fora_do_dominio("Como faço para tirar o passaporte?", alto, ABSTENCAO_LIMIAR_COSSENO)
    # Persona Rafael (Premissa 2): cosseno 0,24, mas o corpus responde (Azevedo et al., 2013).
    assert not fora_do_dominio("Jejum intermitente funciona?", 0.24, ABSTENCAO_LIMIAR_COSSENO)


@pytest.mark.parametrize("pergunta", [
    "Jejum intermitente funciona?", "Como ler o rótulo para identificar um ultraprocessado?",
    "Lanchar entre as refeições faz mal?", "Dormir pouco pode me fazer engordar?", "Qual a importância de beber água?",
])
def test_perguntas_de_nutricao_tem_termo_do_dominio(pergunta):
    assert tem_termo_de_nutricao(pergunta)


@pytest.mark.parametrize("pergunta", [
    "Como faço para tirar o passaporte?", "Qual a capital da Austrália?", "Me explica o teorema de Pitágoras",
])
def test_perguntas_fora_de_nutricao_nao_tem_termo_do_dominio(pergunta):
    assert not tem_termo_de_nutricao(pergunta)


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


def test_pergunta_de_nutricao_com_cosseno_baixo_mantem_os_trechos_da_busca():
    """Revisão do PR #51: o BM25 acha a evidência que o cosseno não vê; ela não pode ser descartada."""
    consultor = _consultor(similaridade=0.24)
    trecho = _trecho()
    consultor.retriever.retrieve.return_value = [trecho]
    resposta = consultor.consult("Jejum intermitente funciona?")
    assert resposta.abstencao is False
    assert consultor.llm_client.generate_structured_synthesis.call_args.kwargs["retrieved_chunks"] == [trecho]


def test_fora_do_dominio_mas_com_grafo_responde_so_com_o_grafo():
    """Decisão de 12/11/2026: grafo ou TACO com resultado respondem mesmo sem evidência do corpus."""
    consultor = _consultor(similaridade=0.10, caminhos_grafo=[_caminho()])
    consultor.retriever.retrieve.return_value = [_trecho()]
    resposta = consultor.consult("Isso funciona mesmo?")
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
