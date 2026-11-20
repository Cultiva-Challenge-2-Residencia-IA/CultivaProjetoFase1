"""Subgrafo do agente de Nutrição (issue #76).

Mesma sequência do consultor antes do LangGraph, sem os portões de risco e de prompt injection,
que ficam no grafo principal (`src/orquestrador/grafo.py`):

guardrail de entrada → busca híbrida → TACO → grafo causal → "não sei" → síntese → guardrail de
saída e montagem da resposta.

Os nós leem os componentes do consultor (`retriever`, `taco_tool`, `graph_engine`,
`llm_client`, `guardrail`) no momento da chamada, e não na construção do grafo. Cada nó abre a
sua observação no Langfuse quando a observabilidade está ligada (`src/observabilidade.py`), aninhada
à observação raiz aberta por `consult()`.
"""

from typing import Any, Dict, List, Optional, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from src.config import ABSTENCAO_LIMIAR_COSSENO
from src.observabilidade import observacao, resumo_trechos
from src.models.schemas import (
    CausalGraphPath,
    ConsultantResponse,
    GuardrailAssessment,
    RetrievedChunk,
    TacoFoodNutrientRecord,
)
from src.rag.abstencao import MENSAGEM_NAO_SEI, fora_do_dominio
from src.rag.verificador.citacoes import MARCADOR, eh_trecho


class EstadoNutricao(TypedDict, total=False):
    # Compartilhados com o grafo principal.
    pergunta: str
    top_k: int
    resposta: Optional[ConsultantResponse]
    # Internos do agente.
    avaliacao: GuardrailAssessment
    pergunta_efetiva: str
    consulta_busca: str
    recuperados: List[RetrievedChunk]
    registros_taco: List[TacoFoodNutrientRecord]
    contexto_taco: str
    caminhos_grafo: List[CausalGraphPath]
    contexto_grafo: str
    similaridade: Optional[float]
    sintese: Dict[str, Any]
    modelo: str
    fundamentacao: Dict[str, Any]


def _respondido(estado: EstadoNutricao) -> bool:
    return estado.get("resposta") is not None


def construir_subgrafo(consultor: Any) -> CompiledStateGraph:
    """Subgrafo que lê `pergunta` e `top_k` e escreve `resposta` (uma `ConsultantResponse`)."""

    def guardrail_entrada(estado: EstadoNutricao) -> dict:
        # Conformidade com a Lei nº 8.234/91: pedidos individuais viram pergunta populacional.
        pergunta = estado["pergunta"]
        with observacao("guardrail_entrada", tipo="guardrail", input={"query": pergunta}) as obs:
            avaliacao = consultor.guardrail.assess_and_reframe(pergunta)
            obs.update(
                output={
                    "restrito_lei_8234": avaliacao.is_restricted_by_law_8234,
                    "intent_category": str(avaliacao.intent_category),
                    "query_reformulada": avaliacao.reframed_population_query,
                }
            )
        efetiva = avaliacao.reframed_population_query
        busca = f"{efetiva} {pergunta}" if avaliacao.is_restricted_by_law_8234 else efetiva
        return {"avaliacao": avaliacao, "pergunta_efetiva": efetiva, "consulta_busca": busca}

    def busca_hibrida(estado: EstadoNutricao) -> dict:
        # BM25 + vetorial local + RRF (ADR 0001). Sem busca só na linha de base "LLM puro" da ablação.
        if not getattr(consultor, "enable_rag", True):
            return {"recuperados": []}
        consulta, top_k = estado["consulta_busca"], estado["top_k"]
        with observacao("retrieve", tipo="retriever", input={"query": consulta, "top_k": top_k}) as obs:
            recuperados = consultor.retriever.retrieve(consulta, top_k=top_k)
            obs.update(output=resumo_trechos(recuperados))
        return {"recuperados": recuperados}

    def tabela_taco(estado: EstadoNutricao) -> dict:
        if consultor.taco_tool is None:
            return {"registros_taco": [], "contexto_taco": ""}
        with observacao("taco", tipo="tool", input={"query": estado["consulta_busca"]}) as obs:
            registros, contexto = consultor.taco_tool.auto_query_from_question(estado["consulta_busca"])
            obs.update(output=[rec.description for rec in registros])
        return {"registros_taco": registros, "contexto_taco": contexto}

    def grafo_causal(estado: EstadoNutricao) -> dict:
        if consultor.graph_engine is None:
            return {"caminhos_grafo": [], "contexto_grafo": ""}
        with observacao("grafo_causal", tipo="tool", input={"query": estado["consulta_busca"]}) as obs:
            caminhos, contexto = consultor.graph_engine.traverse_for_query(estado["consulta_busca"], max_paths=4)
            obs.update(output=contexto)
        return {"caminhos_grafo": caminhos, "contexto_grafo": contexto}

    def abstencao(estado: EstadoNutricao) -> dict:
        # "Não sei" (RF-IA01): fora do domínio (cosseno baixo e nenhum termo de Nutrição), resposta
        # fixa sem LLM. Se o grafo ou a TACO tiverem resultado, responde só com eles. Só com a busca
        # ligada: sem RAG (linha de base "LLM puro" da ablação) não há similaridade a medir.
        if not getattr(consultor, "enable_rag", True):
            return {"similaridade": None}
        similaridade = round(consultor.retriever.similaridade_maxima(estado["consulta_busca"]), 4)
        atualizacao: Dict[str, Any] = {"similaridade": similaridade}
        if fora_do_dominio(estado["pergunta"], similaridade, ABSTENCAO_LIMIAR_COSSENO):
            if not estado["registros_taco"] and not estado["caminhos_grafo"]:
                avaliacao = estado["avaliacao"]
                atualizacao["resposta"] = consultor._resposta_fixa(
                    estado["pergunta"],
                    MENSAGEM_NAO_SEI,
                    guardrail_triggered=avaliacao.is_restricted_by_law_8234,
                    intent_category="NO_EVIDENCE",
                    legal_compliance_notice=avaliacao.legal_notice_required,
                    abstencao=True,
                    similaridade_maxima=similaridade,
                    retrieval_mode="ABSTENTION_FIXED_MESSAGE",
                )
            else:
                atualizacao["recuperados"] = []
        return atualizacao

    def sintese(estado: EstadoNutricao) -> dict:
        # Ollama local, Groq com liberação explícita ou síntese extrativa (ADR 0003).
        with observacao("sintese", input={"query": estado["pergunta_efetiva"]}) as obs:
            resultado, modelo = consultor.llm_client.generate_structured_synthesis(
                query=estado["pergunta_efetiva"],
                retrieved_chunks=estado["recuperados"],
                taco_context_str=estado["contexto_taco"],
                graph_context_str=estado["contexto_grafo"],
                # Só a configuração liga o "LLM puro"; resultado vazio da busca não liga.
                sem_contexto=getattr(consultor, "modo_llm_puro", False),
            )
            obs.update(output=resultado, metadata={"model_used": modelo})
            # Scores do trace para filtrar e montar painéis no Langfuse.
            obs.score_trace(name="modelo_usado", value=modelo, data_type="CATEGORICAL")
            obs.score_trace(
                name="sintese_extrativa",
                value=1.0 if modelo == "local_extractive_synthesis" else 0.0,
                data_type="NUMERIC",
            )
        fundamentacao = resultado.pop("_fundamentacao", {"status": None, "problemas": []})
        atualizacao: Dict[str, Any] = {"sintese": resultado, "modelo": modelo, "fundamentacao": fundamentacao}
        if fundamentacao.get("status") == "llm_sem_base":
            # O LLM leu os Trechos e disse que eles não respondem: "não sei" (RF-IA01).
            avaliacao = estado["avaliacao"]
            atualizacao["resposta"] = consultor._resposta_fixa(
                estado["pergunta"],
                MENSAGEM_NAO_SEI,
                guardrail_triggered=avaliacao.is_restricted_by_law_8234,
                intent_category="NO_EVIDENCE",
                legal_compliance_notice=avaliacao.legal_notice_required,
                abstencao=True,
                similaridade_maxima=estado["similaridade"],
                retrieval_mode="ABSTENTION_FIXED_MESSAGE",
                fundamentacao_status="llm_sem_base",
            )
        return atualizacao

    def resposta(estado: EstadoNutricao) -> dict:
        return {"resposta": _montar_resposta(consultor, estado)}

    grafo = StateGraph(EstadoNutricao)
    for nome, no in (
        ("guardrail_entrada", guardrail_entrada),
        ("busca_hibrida", busca_hibrida),
        ("tabela_taco", tabela_taco),
        ("grafo_causal", grafo_causal),
        ("abstencao", abstencao),
        ("sintese", sintese),
        ("resposta", resposta),
    ):
        grafo.add_node(nome, no)
    grafo.add_edge(START, "guardrail_entrada")
    grafo.add_edge("guardrail_entrada", "busca_hibrida")
    grafo.add_edge("busca_hibrida", "tabela_taco")
    grafo.add_edge("tabela_taco", "grafo_causal")
    grafo.add_edge("grafo_causal", "abstencao")
    grafo.add_conditional_edges("abstencao", lambda e: END if _respondido(e) else "sintese", ["sintese", END])
    grafo.add_conditional_edges("sintese", lambda e: END if _respondido(e) else "resposta", ["resposta", END])
    grafo.add_edge("resposta", END)
    return grafo.compile()


def _montar_resposta(consultor: Any, estado: EstadoNutricao) -> ConsultantResponse:
    """Guardrail de saída, citações, fontes de alimentos e modo de recuperação."""
    sintese = estado["sintese"]
    recuperados = estado["recuperados"]
    caminhos_grafo = estado["caminhos_grafo"]
    registros_taco = estado["registros_taco"]
    avaliacao = estado["avaliacao"]
    fundamentacao = estado["fundamentacao"]

    # Guardrail de saída: sanitização contra linguagem prescritiva individual.
    with observacao("guardrail_saida", tipo="guardrail") as obs:
        brutos = {
            campo: str(sintese.get(campo, ""))
            for campo in ("evidence_summary", "physiological_mechanism", "protocol_findings")
        }
        sanitizados = {campo: consultor.guardrail.sanitize_output_text(texto) for campo, texto in brutos.items()}
        alterados = [campo for campo in brutos if brutos[campo] != sanitizados[campo]]
        obs.update(output={"campos_alterados": alterados})
        obs.score_trace(name="guardrail_saida_alterou", value=1.0 if alterados else 0.0, data_type="NUMERIC")
    evidence_summary = sanitizados["evidence_summary"]
    physiological_mechanism = sanitizados["physiological_mechanism"]
    protocol_findings = sanitizados["protocol_findings"]

    # Citações (issue #12): só os Trechos marcados [T#] no texto final, com o número e a página.
    # O prefixo "[doc_id]" se mantém para o citacoes_validas do benchmark v2.
    texto_final = f"{evidence_summary} {physiological_mechanism} {protocol_findings}"
    numeros = sorted({
        int(m[1:]) for m in MARCADOR.findall(texto_final)
        if eh_trecho(m) and 1 <= int(m[1:]) <= len(recuperados)
    })
    trechos_citados = [recuperados[n - 1].chunk.chunk_id for n in numeros]
    citations: List[str] = []
    por_chave: dict = {}
    for n in numeros:
        c = recuperados[n - 1].chunk
        por_chave.setdefault(f"{c.doc_id}:{c.section_path}", []).append((n, c))
    for itens in por_chave.values():
        c = itens[0][1]
        rotulos = ", ".join(f"T{n}" + (f" p. {ci.pagina_pdf}" if ci.pagina_pdf else "") for n, ci in itens)
        src_meta = []
        link = c.fonte_url or (f"https://doi.org/{c.doi}" if c.doi else None)
        if link:
            src_meta.append(f"Link: {link}")
        if c.doi:
            src_meta.append(f"DOI: {c.doi}")
        if c.licenca:
            src_meta.append(f"Licença: {c.licenca}")
        if c.approval_status:
            src_meta.append(f"Aprovação: {c.approval_status}")
        meta_suffix = f" | {' | '.join(src_meta)}" if src_meta else ""
        citations.append(
            f"[{c.doc_id}] {c.title} — {c.source_organization} ({c.publication_year}), "
            f"Seção: '{c.section_path}' [{rotulos}] (Evidência: {c.evidence_level}{meta_suffix})"
        )

    if caminhos_grafo:
        citations.append(
            f"[KG_4LAYER_PICO_GRADE] Grafo de Conhecimento de 4 Camadas (NetworkX: {len(caminhos_grafo)} cadeias causais Alimento ➔ Composto ➔ Mecanismo ➔ Desfecho)"
        )

    if registros_taco:
        citations.append(
            "[TACO_4ED_UNICAMP] Tabela Brasileira de Composição de Alimentos (TACO 4ª Edição - NEPA/Unicamp & TBCA-USP) — Consulta Determinística por 100g"
        )

    food_list = list(sintese.get("food_sources_or_compounds", []))
    for gp in caminhos_grafo:
        if gp.food_node not in food_list and not gp.is_contraindicated_for_query:
            food_list.append(f"{gp.food_node} ({gp.compound_node})")
    for rec in registros_taco:
        if rec.description not in food_list:
            food_list.append(rec.description)

    if registros_taco and caminhos_grafo:
        mode = "HYBRID_RAG_PLUS_GRAPH_AND_TACO"
    elif caminhos_grafo:
        mode = "HYBRID_RAG_PLUS_GRAPH_TOOL"
    elif registros_taco:
        mode = "HYBRID_RAG_PLUS_TACO_TOOL"
    else:
        mode = "HYBRID_RAG_BASELINE"

    modelo = estado["modelo"]
    return ConsultantResponse(
        original_query=estado["pergunta"],
        effective_query=estado["pergunta_efetiva"],
        guardrail_triggered=avaliacao.is_restricted_by_law_8234,
        intent_category=avaliacao.intent_category,
        legal_compliance_notice=avaliacao.legal_notice_required,
        evidence_summary=evidence_summary,
        physiological_mechanism=physiological_mechanism,
        protocol_findings=protocol_findings,
        food_sources_or_compounds=food_list,
        taco_records=registros_taco,
        graph_paths=caminhos_grafo,
        evidence_grade=str(sintese.get("evidence_grade", "N/A")),
        citations=citations,
        trechos_citados=trechos_citados,
        fundamentacao_status=fundamentacao.get("status"),
        fundamentacao_problemas=list(fundamentacao.get("problemas", [])),
        fundamentacao_frases_removidas=int(fundamentacao.get("frases_removidas", 0)),
        retrieved_chunks=recuperados,
        model_used=modelo,
        retrieval_mode=mode,
        similaridade_maxima=estado["similaridade"],
        **consultor._rastreabilidade([item.chunk for item in recuperados], modelo),
    )
