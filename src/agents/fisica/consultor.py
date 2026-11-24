"""Agente de Saúde Física (issue #99), no mesmo modelo do Agente de Nutrição.

Reaproveita o consultor e o subgrafo de Nutrição (`src/agents/nutricao/grafo.py`) com os
componentes da área: Trechos de `corpus/saudefisica/rag` (fontes aprovadas, gate do ADR 0002), o
guardrail da Lei 9.696/1998, o prompt da área e o vocabulário do "não sei". Não tem TACO nem grafo
causal, e não tem portão próprio: é usado pelo Chat, que aplica os portões antes de qualquer agente.

Desde a issue #105, a busca da área usa por padrão o reranker cross-encoder e o filtro de relevância
antes da síntese (`CULTIVA_RERANKER_SAUDE_FISICA` e `CULTIVA_FILTRO_RELEVANCIA_SAUDE_FISICA`), com a
lacuna explícita quando nenhum Trecho trata da pergunta (eval/relevancia/resultados.md).
"""

import hashlib
import inspect
from typing import List, Optional

from src.agent.consultant_baseline import NutritionConsultantBaseline
from src.agent.llm_client import LocalLLMClient
from src.agents.fisica.guardrail import GuardrailSaudeFisica
from src.agents.fisica.prompt import ROTULO_PERGUNTA_SAUDE_FISICA, SYSTEM_PROMPT_SAUDE_FISICA
from src.config import CORPUS_RAG_DIR_SAUDE_FISICA, INCLUDE_PENDING_SOURCES
from src.models.schemas import DocumentChunk
from src.orquestrador.roteamento import TERMOS_DE_ROTA_SAUDE_FISICA
from src.rag.corpus_loader import carregar_chunks_do_corpus

MENSAGEM_NAO_SEI_SAUDE_FISICA = (
    "Não encontrei nas fontes aprovadas do CULTIVA informação para responder a essa pergunta. Eu só "
    "respondo com base em fontes verificadas sobre atividade física e saúde física, como o Guia de "
    "Atividade Física para a População Brasileira e as diretrizes da OMS.\n\n"
    "Para um plano de exercícios ou uma dor em particular, um profissional de Educação Física ou um "
    "fisioterapeuta pode ajudar."
)

PROMPT_VERSION_SAUDE_FISICA = hashlib.sha256(
    (SYSTEM_PROMPT_SAUDE_FISICA + inspect.getsource(LocalLLMClient._build_user_prompt)).encode("utf-8")
).hexdigest()


class ConsultorSaudeFisica(NutritionConsultantBaseline):
    area = "saude_fisica"
    termos_dominio = TERMOS_DE_ROTA_SAUDE_FISICA
    mensagem_nao_sei = MENSAGEM_NAO_SEI_SAUDE_FISICA
    prompt_version = PROMPT_VERSION_SAUDE_FISICA

    def __init__(
        self,
        chunks: Optional[List[DocumentChunk]] = None,
        incluir_pendentes: bool = INCLUDE_PENDING_SOURCES,
        enable_ollama: bool = True,
    ) -> None:
        if chunks is None:
            chunks = carregar_chunks_do_corpus(incluir_pendentes=incluir_pendentes,
                                               rag_dir=CORPUS_RAG_DIR_SAUDE_FISICA)
        super().__init__(
            chunks=chunks,
            incluir_pendentes=incluir_pendentes,
            enable_ollama=enable_ollama,
            enable_taco_tool=False,
            enable_graph_engine=False,
            com_portao_de_risco=False,
        )
        self.guardrail = GuardrailSaudeFisica()
        self.llm_client = LocalLLMClient(
            enable_ollama=enable_ollama,
            system_prompt=SYSTEM_PROMPT_SAUDE_FISICA,
            rotulo_pergunta=ROTULO_PERGUNTA_SAUDE_FISICA,
        )
