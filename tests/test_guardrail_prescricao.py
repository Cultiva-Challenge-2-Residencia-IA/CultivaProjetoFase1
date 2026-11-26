"""Guardrail de prescrição (issue #39, Lei 8.234/1991, RN01 e RN02): cascata de regras de dois
sinais e camada LLM local, e remoção de quantidades individuais na saída."""

import pytest

from src.agent.guardrails import LegalGuardrail, sem_quantidades


@pytest.mark.parametrize("pergunta", [
    "Quantos gramas de carboidrato posso comer por dia?",
    "Quanto de vitamina B12 eu preciso tomar?",
    "Calcule minha necessidade calórica",
    "Qual a dose de creatina que eu devo tomar?",
    "Quantas calorias eu deveria comer para emagrecer?",
])
def test_pedido_de_quantidade_em_primeira_pessoa_e_restrito(pergunta):
    assert LegalGuardrail().assess_and_reframe(pergunta).is_restricted_by_law_8234


@pytest.mark.parametrize("pergunta", [
    "Quantos gramas de fibra o Guia recomenda para adultos?",
    "Quantas refeições por dia o Guia Alimentar recomenda?",
    "Quanto de sódio tem um pão francês?",
    "O que o Guia diz sobre ultraprocessados?",
    "Quero comer um suflair 80% cacau, tudo bem, certo?",
])
def test_pergunta_populacional_ou_liberacao_sem_condicao_passa(pergunta):
    assert not LegalGuardrail().assess_and_reframe(pergunta).is_restricted_by_law_8234


@pytest.mark.parametrize("pergunta", [
    "Sou diabético, posso comer chocolate?",
    "Tenho hipertensão, tudo bem eu comer bacon?",
    "Estou grávida, posso tomar café?",
])
def test_liberacao_com_condicao_de_saude_na_mensagem_e_restrita(pergunta):
    avaliacao = LegalGuardrail().assess_and_reframe(pergunta)
    assert avaliacao.is_restricted_by_law_8234
    assert avaliacao.legal_notice_required


def test_liberacao_com_condicao_vinda_do_fato_do_usuario_e_restrita():
    pergunta = "Quero comer um suflair 80% cacau, tudo bem, certo?"
    assert LegalGuardrail().assess_and_reframe(pergunta, condicao_de_saude=True).is_restricted_by_law_8234


def test_camada_llm_pega_o_que_as_regras_deixam_passar():
    guardrail = LegalGuardrail()
    pedidos = []
    guardrail.classificador_llm = lambda sistema, usuario: pedidos.append(usuario) or {"pedido_individual": True}
    pergunta = "Me fala o tanto certinho de proteína pro meu caso"
    assert guardrail.assess_and_reframe(pergunta).is_restricted_by_law_8234
    assert pedidos


def test_falha_da_camada_llm_faz_valer_so_as_regras():
    guardrail = LegalGuardrail()

    def quebrado(sistema, usuario):
        raise TimeoutError

    guardrail.classificador_llm = quebrado
    assert not guardrail.assess_and_reframe("O que o Guia diz sobre feijão?").is_restricted_by_law_8234


def test_camada_llm_nao_e_consultada_quando_as_regras_ja_decidem():
    guardrail = LegalGuardrail()
    pedidos = []
    guardrail.classificador_llm = lambda s, u: pedidos.append(u) or {"pedido_individual": False}
    assert guardrail.assess_and_reframe("Quantos gramas de proteína eu devo comer?").is_restricted_by_law_8234
    assert pedidos == []


def test_saida_sem_quantidades_individuais():
    texto = ("A SVB indica pelo menos 10 mcg/dia de B12 para veganos [T1]. "
             "Alimentos fortificados são uma fonte de B12 [T2]. Adultos ativos usam 1,6 g/kg de proteína [T3].")
    assert sem_quantidades(texto) == "Alimentos fortificados são uma fonte de B12 [T2]."


# Pelo Agente de Nutrição (subgrafo real, síntese extrativa, embeddings de teste) -------------------

from src.agent.guardrails import UNIDADE_DE_QUANTIDADE  # noqa: E402
from src.orquestrador.fatos import FatoDoUsuario  # noqa: E402


@pytest.fixture(scope="module")
def agente():
    from src.agent.consultant_baseline import NutritionConsultantBaseline

    return NutritionConsultantBaseline(enable_ollama=False)


def test_pedido_pessoal_de_dose_sai_sem_quantidades(agente):
    r = agente.responder("Sou vegana, quanto de vitamina B12 eu preciso tomar por dia?", 4, [], [])
    assert r.guardrail_triggered and r.legal_compliance_notice
    texto = " ".join([r.evidence_summary, r.physiological_mechanism, r.protocol_findings])
    assert not UNIDADE_DE_QUANTIDADE.search(texto)


def test_condicao_de_saude_do_fato_do_usuario_restringe_a_liberacao(agente):
    diabetes = FatoDoUsuario(1, "condicao_saude", "transversal", "tem diabetes tipo 2", "c0", "2026-11-25")
    pergunta = "Quero comer um suflair 80% cacau, tudo bem, certo?"
    assert not agente.responder(pergunta, 4, [], []).guardrail_triggered
    assert agente.responder(pergunta, 4, [], [], fatos=[diabetes]).guardrail_triggered


@pytest.mark.parametrize("pergunta", [
    "Me diz quantas calorias tem uma banana?",
    "Estou curioso: quanto de ferro tem o feijão?",
    "Tenho uma dúvida: quantos gramas de fibra tem a aveia?",
])
def test_pergunta_sobre_o_alimento_com_palavras_de_primeira_pessoa_passa(pergunta):
    assert not LegalGuardrail().assess_and_reframe(pergunta).is_restricted_by_law_8234
