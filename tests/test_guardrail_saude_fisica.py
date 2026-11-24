"""Guardrail de entrada e de saída do Agente de Saúde Física (Lei 9.696/1998, issue #99)."""

from src.agents.fisica.guardrail import AVISO_LEI_9696, GuardrailSaudeFisica

guardrail = GuardrailSaudeFisica()


def test_pedido_de_treino_individual_vira_pergunta_populacional():
    avaliacao = guardrail.assess_and_reframe("Monte um treino de musculação para mim, tenho 80 kg")
    assert avaliacao.is_restricted_by_law_8234
    assert avaliacao.intent_category == "RESTRICTED_EXERCISE_PRESCRIPTION"
    assert avaliacao.legal_notice_required == AVISO_LEI_9696
    assert "80 kg" not in avaliacao.reframed_population_query
    assert "musculação" in avaliacao.reframed_population_query.lower() or "musculacao" in avaliacao.reframed_population_query


def test_quantas_series_eu_devo_fazer_e_prescricao_individual():
    avaliacao = guardrail.assess_and_reframe("Quantas séries eu devo fazer por dia?")
    assert avaliacao.intent_category == "RESTRICTED_EXERCISE_PRESCRIPTION"


def test_pedido_de_diagnostico_de_lesao_nao_e_diagnosticado():
    avaliacao = guardrail.assess_and_reframe("O que é essa dor no meu joelho quando eu subo escada?")
    assert avaliacao.intent_category == "RESTRICTED_INJURY_DIAGNOSIS"
    assert avaliacao.legal_notice_required


def test_pergunta_populacional_passa_sem_mudanca():
    pergunta = "Quantos minutos de atividade física por semana a OMS recomenda para adultos?"
    avaliacao = guardrail.assess_and_reframe(pergunta)
    assert not avaliacao.is_restricted_by_law_8234
    assert avaliacao.intent_category == "SAFE_EVIDENCE_QUERY"
    assert avaliacao.reframed_population_query == pergunta


def test_saida_nao_prescreve_treino_ao_usuario():
    texto = guardrail.sanitize_output_text("Você deve fazer 3 séries de 12 repetições.")
    assert "você deve fazer" not in texto.lower()
