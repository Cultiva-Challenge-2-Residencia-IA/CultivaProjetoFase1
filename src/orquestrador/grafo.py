"""Grafo principal do CULTIVA (issue #76): portões de segurança e chamada do agente.

Os portões de risco (RF-IA03) e de prompt injection (RNF04) ficam aqui, fora de qualquer agente,
para valerem para todos os que entrarem no grafo. Hoje há um só agente, o de Nutrição; o
roteamento entre agentes fica para quando o de Saúde Física existir.
"""

from typing import Callable, Mapping, Optional, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from src.agent.guardrails import LAW_8234_COMPLIANCE_NOTICE
from src.guardrails.injection import MENSAGEM_INJECAO, has_prompt_injection
from src.guardrails.risco import MENSAGEM_ACOLHIMENTO, detectar_risco
from src.models.schemas import ConsultantResponse

RespostaFixa = Callable[..., ConsultantResponse]


class EstadoOrquestrador(TypedDict, total=False):
    """Estado compartilhado com os agentes: só a pergunta, o `top_k` e a resposta final."""

    pergunta: str
    top_k: int
    resposta: Optional[ConsultantResponse]


def _respondido(estado: EstadoOrquestrador) -> bool:
    return estado.get("resposta") is not None


def construir_grafo(
    agentes: Mapping[str, CompiledStateGraph],
    resposta_fixa: RespostaFixa,
    agente_padrao: str,
) -> CompiledStateGraph:
    """Monta START → risco → prompt injection → agente → END.

    `agentes` mapeia o nome do nó para o subgrafo compilado de cada agente; o subgrafo precisa
    ler `pergunta` e `top_k` e escrever `resposta`. `resposta_fixa` monta as respostas sem LLM
    dos portões, com os campos de rastreabilidade (#11).
    """
    if agente_padrao not in agentes:
        raise ValueError(f"Agente padrão '{agente_padrao}' não está entre {sorted(agentes)}.")

    def portao_risco(estado: EstadoOrquestrador) -> dict:
        risco = detectar_risco(estado["pergunta"])
        if not risco.risco:
            return {"resposta": None}
        return {"resposta": resposta_fixa(
            estado["pergunta"],
            MENSAGEM_ACOLHIMENTO,
            guardrail_triggered=False,
            intent_category="RISK_SUPPORT",
            risk_triggered=True,
            risk_categories=risco.categorias,
            retrieval_mode="RISK_FIXED_MESSAGE",
        )}

    def portao_injecao(estado: EstadoOrquestrador) -> dict:
        if not has_prompt_injection(estado["pergunta"]):
            return {"resposta": None}
        return {"resposta": resposta_fixa(
            estado["pergunta"],
            MENSAGEM_INJECAO,
            guardrail_triggered=True,
            intent_category="PROMPT_INJECTION_BLOCKED",
            legal_compliance_notice=LAW_8234_COMPLIANCE_NOTICE,
            prompt_injection_detected=True,
            retrieval_mode="PROMPT_INJECTION_FIXED_MESSAGE",
        )}

    grafo = StateGraph(EstadoOrquestrador)
    grafo.add_node("portao_risco", portao_risco)
    grafo.add_node("portao_injecao", portao_injecao)
    for nome, subgrafo in agentes.items():
        grafo.add_node(nome, subgrafo)
        grafo.add_edge(nome, END)

    grafo.add_edge(START, "portao_risco")
    grafo.add_conditional_edges(
        "portao_risco", lambda e: END if _respondido(e) else "portao_injecao", ["portao_injecao", END]
    )
    grafo.add_conditional_edges(
        "portao_injecao", lambda e: END if _respondido(e) else agente_padrao, [agente_padrao, END]
    )
    return grafo.compile()
