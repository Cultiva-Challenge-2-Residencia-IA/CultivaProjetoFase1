"""Grafo principal do CULTIVA (issue #76): portões de segurança e chamada do agente.

Os portões de risco (RF-IA03) e de prompt injection (RNF04) ficam aqui, fora de qualquer agente,
para valerem para todos os que entrarem no grafo. O portão de risco usa o léxico como piso e, quando
ele não aciona, a camada LLM local opcional (`classificador_llm.py`, issue #48); sem ela (CI,
benchmark, testes), vale só o léxico. Hoje há um só agente, o de Nutrição; o
roteamento entre agentes fica para quando o de Saúde Física existir.
"""

from typing import Callable, List, Mapping, Optional, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from src.agent.guardrails import LAW_8234_COMPLIANCE_NOTICE
from src.guardrails.injection import MENSAGEM_INJECAO, has_prompt_injection
from src.guardrails.risco import MENSAGEM_ACOLHIMENTO, detectar_risco
from src.guardrails.risco.classificador_llm import ClassificadorRiscoLLM
from src.models.schemas import ConsultantResponse

RespostaFixa = Callable[..., ConsultantResponse]


class EstadoOrquestrador(TypedDict, total=False):
    """Estado compartilhado com os agentes: a pergunta, o `top_k` e a resposta final.

    `risco_llm_status` é a situação da camada LLM de risco nesta pergunta: None (desligada),
    "ok" (consultada) ou "falhou" (Ollama fora, tempo limite ou saída inválida; valeu o léxico).
    """

    pergunta: str
    top_k: int
    resposta: Optional[ConsultantResponse]
    risco_llm_status: Optional[str]


def _respondido(estado: EstadoOrquestrador) -> bool:
    return estado.get("resposta") is not None


def construir_grafo(
    agentes: Mapping[str, CompiledStateGraph],
    resposta_fixa: RespostaFixa,
    agente_padrao: str,
    risco_llm: Optional[ClassificadorRiscoLLM] = None,
) -> CompiledStateGraph:
    """Monta START → risco → prompt injection → agente → END.

    `agentes` mapeia o nome do nó para o subgrafo compilado de cada agente; o subgrafo precisa
    ler `pergunta` e `top_k` e escrever `resposta`. `resposta_fixa` monta as respostas sem LLM
    dos portões, com os campos de rastreabilidade (#11). `risco_llm`, quando dado, só é consultado
    se o léxico não acionar; ele pode acrescentar detecções, nunca removê-las.
    """
    if agente_padrao not in agentes:
        raise ValueError(f"Agente padrão '{agente_padrao}' não está entre {sorted(agentes)}.")

    def portao_risco(estado: EstadoOrquestrador) -> dict:
        risco = detectar_risco(estado["pergunta"])
        categorias: List[str] = risco.categorias
        camada, status_llm = "lexico", None
        if not risco.risco and risco_llm is not None:
            resultado = risco_llm.classificar(estado["pergunta"])
            status_llm = "falhou" if resultado is None else "ok"
            if resultado is not None and resultado.risco:
                categorias, camada = resultado.categorias, "llm"
        if not categorias:
            return {"resposta": None, "risco_llm_status": status_llm}
        return {"risco_llm_status": status_llm, "resposta": resposta_fixa(
            estado["pergunta"],
            MENSAGEM_ACOLHIMENTO,
            guardrail_triggered=False,
            intent_category="RISK_SUPPORT",
            risk_triggered=True,
            risk_categories=categorias,
            risk_layer=camada,
            risk_llm_status=status_llm,
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
