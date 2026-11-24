"""Serviço de chat (issue #99): portões, roteamento, Sincronizador, Histórico e exclusão.

Os Agentes de área e o LLM são falsos: o teste olha o comportamento do Chat geral e dos Chats de
área, não a qualidade da busca.
"""

from typing import List, Optional

import pytest

from src.chat.historico import HistoricoSQLite
from src.chat.servico import CHAT_GERAL, ServicoDeChat
from src.guardrails.alerta import MENSAGEM_ALERTA
from src.guardrails.risco import MENSAGEM_ACOLHIMENTO
from src.models.schemas import ConsultantResponse
from src.orquestrador.reescrita import Mensagem
from src.orquestrador.roteamento import AREA_NUTRICAO, AREA_SAUDE_FISICA


class AgenteFalso:
    def __init__(self, area: str):
        self.area = area
        self.chamadas: List[dict] = []

    def responder(self, pergunta: str, top_k: int, consultas_extras: List[str],
                  historico: List[Mensagem]) -> ConsultantResponse:
        self.chamadas.append({"pergunta": pergunta, "extras": consultas_extras, "historico": historico})
        return ConsultantResponse(
            response_id=f"r-{self.area}-{len(self.chamadas)}", original_query=pergunta, effective_query=pergunta,
            guardrail_triggered=False, intent_category="SAFE_EVIDENCE_QUERY",
            evidence_summary=f"Resposta de {self.area}.", physiological_mechanism="", protocol_findings="",
            evidence_grade="N/A", corpus_version="c", prompt_version="p", model_version="m", fontes_version="f",
        )


@pytest.fixture
def agentes():
    return {AREA_NUTRICAO: AgenteFalso(AREA_NUTRICAO), AREA_SAUDE_FISICA: AgenteFalso(AREA_SAUDE_FISICA)}


def _servico(tmp_path, agentes, llm=None) -> ServicoDeChat:
    return ServicoDeChat(agentes=agentes, historico=HistoricoSQLite(tmp_path / "conversas.sqlite3"), llm=llm)


def test_mensagem_de_risco_recebe_acolhimento_sem_agente_e_sem_texto_guardado(tmp_path, agentes):
    servico = _servico(tmp_path, agentes)
    mensagem = "Vomito depois de comer para não engordar."
    resposta = servico.enviar(CHAT_GERAL, "u1", "c1", mensagem)
    assert resposta.tipo == "risco"
    assert resposta.texto == MENSAGEM_ACOLHIMENTO
    assert not any(a.chamadas for a in agentes.values())
    guardadas = servico.historico.recentes("u1", "c1", limite=10)
    assert mensagem not in " ".join(m.texto for m in guardadas)


def test_sinal_de_alerta_vale_tambem_no_chat_de_nutricao(tmp_path, agentes):
    resposta = _servico(tmp_path, agentes).enviar(AREA_NUTRICAO, "u1", "c1", "Senti dor no peito forte correndo")
    assert resposta.tipo == "alerta"
    assert resposta.texto == MENSAGEM_ALERTA


def test_chat_geral_manda_pergunta_de_uma_area_so_para_o_agente_dela(tmp_path, agentes):
    resposta = _servico(tmp_path, agentes).enviar(CHAT_GERAL, "u1", "c1", "Quais alimentos têm fibra?")
    assert resposta.areas == [AREA_NUTRICAO]
    assert agentes[AREA_NUTRICAO].chamadas and not agentes[AREA_SAUDE_FISICA].chamadas


def test_chat_geral_sem_llm_aciona_as_duas_areas_e_deixa_lado_a_lado(tmp_path, agentes):
    resposta = _servico(tmp_path, agentes).enviar(
        CHAT_GERAL, "u1", "c1", "O que comer antes do treino de musculação?")
    assert set(resposta.areas) == {AREA_NUTRICAO, AREA_SAUDE_FISICA}
    assert resposta.modo_sincronizacao == "lado_a_lado"
    assert "Resposta de nutricao." in resposta.texto and "Resposta de saude_fisica." in resposta.texto


def test_chat_de_area_indica_o_chat_certo_para_pergunta_da_outra_area(tmp_path, agentes):
    resposta = _servico(tmp_path, agentes).enviar(
        AREA_NUTRICAO, "u1", "c1", "Quantas séries de agachamento são recomendadas para iniciantes?")
    assert resposta.tipo == "outra_area"
    assert "Saúde Física" in resposta.texto
    assert not agentes[AREA_NUTRICAO].chamadas


def test_chat_de_area_responde_a_parte_dele_e_indica_o_resto(tmp_path, agentes):
    resposta = _servico(tmp_path, agentes).enviar(
        AREA_NUTRICAO, "u1", "c1", "O que comer antes do treino de musculação?")
    assert resposta.areas == [AREA_NUTRICAO]
    assert resposta.redirecionamento and "Saúde Física" in resposta.redirecionamento
    assert not agentes[AREA_SAUDE_FISICA].chamadas


def test_pergunta_fora_das_areas_recebe_nao_sei_quando_o_llm_decide(tmp_path, agentes):
    llm = lambda _s, _u: {"pergunta_completa": "Quem ganhou o jogo?", "subperguntas": []}  # noqa: E731
    resposta = _servico(tmp_path, agentes, llm=llm).enviar(CHAT_GERAL, "u1", "c1", "Quem ganhou o jogo ontem?")
    assert resposta.tipo == "fora_das_areas"
    assert not any(a.chamadas for a in agentes.values())


def test_pergunta_de_estudos_diz_que_a_area_ainda_nao_tem_agente(tmp_path, agentes):
    resposta = _servico(tmp_path, agentes).enviar(CHAT_GERAL, "u1", "c1", "Como organizar meus estudos para a prova?")
    assert resposta.tipo == "fora_das_areas"
    assert "Estudos" in resposta.texto


def test_continuacao_chega_ao_llm_com_o_historico(tmp_path, agentes):
    vistos: List[str] = []

    def llm(sistema: str, usuario: str) -> Optional[dict]:
        if "prepara buscas" not in sistema:
            return None
        vistos.append(usuario)
        return {"pergunta_completa": "Quais alimentos ajudam quem tem hipertensão?", "subperguntas": [
            {"area": "nutricao", "pergunta": "Quais alimentos ajudam quem tem hipertensão?",
             "trecho_hipotetico": "O padrão DASH reduz a pressão."}]}

    servico = _servico(tmp_path, agentes, llm=llm)
    servico.hyde_na_busca = True  # o trecho hipotético só vai à busca com a flag (desligada por padrão)
    servico.enviar(CHAT_GERAL, "u1", "c1", "Tenho hipertensão, o que comer?")
    servico.enviar(CHAT_GERAL, "u1", "c1", "E quais evitar?")
    assert "Tenho hipertensão" in vistos[-1]
    ultima = agentes[AREA_NUTRICAO].chamadas[-1]
    assert ultima["pergunta"] == "Quais alimentos ajudam quem tem hipertensão?"
    assert "O padrão DASH reduz a pressão." in ultima["extras"]


def test_chat_geral_le_os_chats_de_area_e_cada_agente_recebe_so_a_sua_area(tmp_path, agentes):
    servico = _servico(tmp_path, agentes)
    servico.enviar(AREA_SAUDE_FISICA, "u1", "c-fisica", "Quantos minutos de caminhada por semana?")
    servico.enviar(AREA_NUTRICAO, "u1", "c-nutri", "Quais alimentos têm fibra?")
    servico.enviar(CHAT_GERAL, "u1", "c-geral", "O que comer antes do treino de musculação?")
    historico_nutri = agentes[AREA_NUTRICAO].chamadas[-1]["historico"]
    textos = " ".join(m.texto for m in historico_nutri)
    assert "fibra" in textos
    assert "caminhada" not in textos
    assert all(m.area in (None, AREA_NUTRICAO) for m in historico_nutri)


def test_chat_de_area_nao_le_o_chat_geral(tmp_path, agentes):
    servico = _servico(tmp_path, agentes)
    servico.enviar(CHAT_GERAL, "u1", "c-geral", "Quais alimentos têm ferro?")
    servico.enviar(AREA_NUTRICAO, "u1", "c-nutri", "Quais alimentos têm fibra?")
    historico = agentes[AREA_NUTRICAO].chamadas[-1]["historico"]
    assert "ferro" not in " ".join(m.texto for m in historico)


def test_apagar_conversa_remove_o_historico(tmp_path, agentes):
    servico = _servico(tmp_path, agentes)
    servico.enviar(CHAT_GERAL, "u1", "c1", "Quais alimentos têm fibra?")
    servico.apagar_conversa("u1", "c1")
    assert servico.historico.recentes("u1", "c1", limite=10) == []


def test_apagar_usuario_remove_todas_as_conversas(tmp_path, agentes):
    servico = _servico(tmp_path, agentes)
    servico.enviar(CHAT_GERAL, "u1", "c1", "Quais alimentos têm fibra?")
    servico.enviar(AREA_NUTRICAO, "u1", "c2", "Quais alimentos têm ferro?")
    servico.apagar_usuario("u1")
    assert servico.historico.recentes("u1", "c1", limite=10) == []
    assert servico.historico.recentes("u1", "c2", limite=10) == []


def test_pedido_restrito_pela_lei_da_area_traz_a_nota_legal(tmp_path, agentes):
    class AgenteComGuardrail(AgenteFalso):
        def responder(self, pergunta, top_k, consultas_extras, historico):
            resposta = super().responder(pergunta, top_k, consultas_extras, historico)
            return resposta.model_copy(update={"guardrail_triggered": True,
                                               "legal_compliance_notice": "Nota da Lei 9.696/1998."})

    agentes[AREA_SAUDE_FISICA] = AgenteComGuardrail(AREA_SAUDE_FISICA)
    resposta = _servico(tmp_path, agentes).enviar(AREA_SAUDE_FISICA, "u1", "c1", "Monte um treino de musculação para mim")
    assert resposta.texto.startswith("Nota da Lei 9.696/1998.")


def test_sem_a_flag_o_trecho_hipotetico_nao_vai_para_a_busca(tmp_path, agentes):
    def llm(sistema, usuario):
        if "prepara buscas" not in sistema:
            return None
        return {"pergunta_completa": "Quais alimentos têm fibra?", "subperguntas": [
            {"area": "nutricao", "pergunta": "Quais alimentos têm fibra?", "trecho_hipotetico": "Fibras estão em grãos."}]}

    servico = _servico(tmp_path, agentes, llm=llm)
    servico.enviar(CHAT_GERAL, "u1", "c1", "Quais alimentos são ricos em fibra?")
    chamada = agentes[AREA_NUTRICAO].chamadas[-1]
    assert chamada["extras"] == []
    assert chamada["pergunta"] == "Quais alimentos são ricos em fibra?"  # sem Histórico, a mensagem como veio
