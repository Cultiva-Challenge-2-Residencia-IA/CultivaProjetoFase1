"""Conversa social: regras de reserva, checagem da resposta do LLM e uso no chat."""

from typing import Optional

import pytest

from src.chat.historico import HistoricoSQLite
from src.chat.servico import CHAT_GERAL, ServicoDeChat
from src.orquestrador.conversa import CONVITES, resposta_social_valida, tipo_social
from src.orquestrador.roteamento import AREA_NUTRICAO, AREA_SAUDE_FISICA
from tests.test_chat import AgenteFalso


@pytest.mark.parametrize("mensagem, tipo", [
    ("Salve", "saudacao"), ("e aí, beleza?", "saudacao"), ("fala aí", "saudacao"),
    ("como vc tá?", "como_vai"), ("td bem?", "como_vai"), ("tudo certo?", "como_vai"),
    ("valeu!", "agradecimento"), ("vlw", "agradecimento"), ("tchau", "despedida"),
    ("quem é você?", "apresentacao"),
])
def test_regras_reconhecem_formas_comuns(mensagem, tipo):
    assert tipo_social(mensagem) == tipo


@pytest.mark.parametrize("mensagem", ["quero ganhar massa", "Olá, quero treinar perna", "salve, quanto de proteína?"])
def test_mensagem_com_assunto_nao_e_social(mensagem):
    assert tipo_social(mensagem) is None


def test_resposta_do_llm_so_passa_se_for_so_conversa():
    assert resposta_social_valida("Salve! Tudo certo por aqui.") == "Salve! Tudo certo por aqui."
    assert resposta_social_valida("Tudo ótimo! Hoje é um bom dia para treinar.") is None  # termo de área
    assert resposta_social_valida("Tudo certo! Beba 2 litros de água.") is None  # número e área
    assert resposta_social_valida("Oi! Qual é o seu peso?") is None  # dado pessoal
    assert resposta_social_valida("Oi! " * 80) is None
    assert resposta_social_valida(None) is None


def _llm_social(tipo: str, resposta: str):
    def llm(sistema: str, usuario: str) -> Optional[dict]:
        if "prepara buscas" not in sistema:
            return None
        return {"pergunta_completa": "x", "subperguntas": [], "esclarecimento": None,
                "conversa_social": {"tipo": tipo, "resposta": resposta}}
    return llm


@pytest.fixture
def agentes():
    return {AREA_NUTRICAO: AgenteFalso(AREA_NUTRICAO), AREA_SAUDE_FISICA: AgenteFalso(AREA_SAUDE_FISICA)}


def _servico(tmp_path, agentes, llm):
    return ServicoDeChat(agentes=agentes, historico=HistoricoSQLite(tmp_path / "c.sqlite3"), llm=llm)


def test_primeira_mensagem_social_e_a_apresentacao_sem_esperar_o_llm(tmp_path, agentes):
    chamadas = []

    def llm(sistema, usuario):
        chamadas.append(sistema)
        return None

    resposta = _servico(tmp_path, agentes, llm).enviar(AREA_SAUDE_FISICA, "u1", "c1", "olá")
    assert resposta.tipo == "conversa" and "Saúde Física" in resposta.texto
    assert not any("prepara buscas" in s for s in chamadas)


def test_conversa_no_meio_usa_a_resposta_do_llm_com_o_convite(tmp_path, agentes):
    servico = _servico(tmp_path, agentes, _llm_social("como_vai", "Tudo certo por aqui, e com você?"))
    servico.enviar(AREA_SAUDE_FISICA, "u1", "c1", "olá")
    resposta = servico.enviar(AREA_SAUDE_FISICA, "u1", "c1", "como vc estśa?")
    assert resposta.tipo == "conversa"
    assert resposta.texto == "Tudo certo por aqui, e com você?"
    assert not any(a.chamadas for a in agentes.values())


def test_resposta_do_llm_reprovada_vira_a_fixa(tmp_path, agentes):
    servico = _servico(tmp_path, agentes, _llm_social("saudacao", "Salve! Bora treinar 5 vezes na semana."))
    servico.enviar(AREA_SAUDE_FISICA, "u1", "c1", "olá")
    resposta = servico.enviar(AREA_SAUDE_FISICA, "u1", "c1", "salve")
    assert resposta.texto == f"Oi! {CONVITES[AREA_SAUDE_FISICA]}"


def test_llm_marcando_social_numa_pergunta_com_termo_de_area_nao_vale(tmp_path, agentes):
    servico = _servico(tmp_path, agentes, _llm_social("saudacao", "Oi!"))
    servico.enviar(CHAT_GERAL, "u1", "c1", "olá")
    resposta = servico.enviar(CHAT_GERAL, "u1", "c1", "salve, como faço para ganhar massa no treino?")
    assert resposta.tipo == "agente"


def test_sem_llm_as_regras_respondem_curto_depois_da_primeira(tmp_path, agentes):
    servico = _servico(tmp_path, agentes, None)
    servico.enviar(AREA_NUTRICAO, "u1", "c1", "oi")
    resposta = servico.enviar(AREA_NUTRICAO, "u1", "c1", "valeu!")
    assert resposta.texto == f"Por nada! {CONVITES[AREA_NUTRICAO]}"


def test_objeto_social_sozinho_tambem_vale():
    from src.orquestrador.reescrita import reescrever
    r = reescrever("salve", [], lambda s, u: {"tipo": "saudacao", "resposta": "E aí!"})
    assert r.origem == "llm" and r.social == ("saudacao", "E aí!") and not r.subperguntas
