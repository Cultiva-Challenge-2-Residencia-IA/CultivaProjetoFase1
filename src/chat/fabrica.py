"""Monta o serviço de chat com os Agentes de área reais (issue #99)."""

import sys
import time
from typing import Iterable, Optional

from src.agent.consultant_baseline import NutritionConsultantBaseline
from src.agent.llm_json import ClienteJsonOllama
from src.agents.fisica.consultor import ConsultorSaudeFisica
from src.chat.historico import HistoricoSQLite
from src.chat.servico import ServicoDeChat
from src.config import HISTORICO_DB_PATH, INCLUDE_PENDING_SOURCES, OLLAMA_NUM_PREDICT, REESCRITA_LLM
from src.orquestrador.roteamento import AREA_NUTRICAO, AREA_SAUDE_FISICA


def pre_carregar_rerankers(agentes: Iterable) -> None:
    """Carrega o reranker cross-encoder dos agentes que o usam (issue #121), cada objeto uma vez, para a
    primeira pergunta não esperar a carga (e, na primeira vez na máquina, o download de cerca de 1 GB)."""
    vistos = set()
    for agente in agentes:
        reranker = getattr(agente, "reranker_cruzado", None)
        if reranker is None or id(reranker) in vistos:
            continue
        vistos.add(id(reranker))
        inicio = time.perf_counter()
        reranker.carregar()
        print(f"Reranker {reranker.modelo} pronto em {time.perf_counter() - inicio:.1f} s.", file=sys.stderr, flush=True)


def criar_servico(enable_ollama: bool = True, incluir_pendentes: bool = INCLUDE_PENDING_SOURCES,
                  historico: Optional[HistoricoSQLite] = None) -> ServicoDeChat:
    nutricao = NutritionConsultantBaseline(enable_ollama=enable_ollama, incluir_pendentes=incluir_pendentes)
    fisica = ConsultorSaudeFisica(enable_ollama=enable_ollama, incluir_pendentes=incluir_pendentes)
    pre_carregar_rerankers([nutricao, fisica])
    llm = None
    if enable_ollama:
        # O mesmo limite de saída da síntese: com 1024, o JSON do Sincronizador chegou a ser cortado (#107).
        cliente = ClienteJsonOllama("reescrita_e_sincronizador", num_predict=OLLAMA_NUM_PREDICT)
        llm = cliente if cliente.disponivel() else None
    return ServicoDeChat(
        agentes={AREA_NUTRICAO: nutricao, AREA_SAUDE_FISICA: fisica},
        historico=historico or HistoricoSQLite(HISTORICO_DB_PATH),
        llm=llm,
        risco_llm=nutricao.risco_llm,
        reescrita_com_llm=REESCRITA_LLM,
    )
