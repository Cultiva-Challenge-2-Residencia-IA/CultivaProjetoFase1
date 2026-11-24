"""Monta o serviço de chat com os Agentes de área reais (issue #99)."""

from typing import Optional

from src.agent.consultant_baseline import NutritionConsultantBaseline
from src.agent.llm_json import ClienteJsonOllama
from src.agents.fisica.consultor import ConsultorSaudeFisica
from src.chat.historico import HistoricoSQLite
from src.chat.servico import ServicoDeChat
from src.config import HISTORICO_DB_PATH, INCLUDE_PENDING_SOURCES, REESCRITA_LLM
from src.orquestrador.roteamento import AREA_NUTRICAO, AREA_SAUDE_FISICA


def criar_servico(enable_ollama: bool = True, incluir_pendentes: bool = INCLUDE_PENDING_SOURCES,
                  historico: Optional[HistoricoSQLite] = None) -> ServicoDeChat:
    nutricao = NutritionConsultantBaseline(enable_ollama=enable_ollama, incluir_pendentes=incluir_pendentes)
    fisica = ConsultorSaudeFisica(enable_ollama=enable_ollama, incluir_pendentes=incluir_pendentes)
    llm = None
    if enable_ollama:
        cliente = ClienteJsonOllama("reescrita_e_sincronizador")
        llm = cliente if cliente.disponivel() else None
    return ServicoDeChat(
        agentes={AREA_NUTRICAO: nutricao, AREA_SAUDE_FISICA: fisica},
        historico=historico or HistoricoSQLite(HISTORICO_DB_PATH),
        llm=llm,
        risco_llm=nutricao.risco_llm,
        reescrita_com_llm=REESCRITA_LLM,
    )
