from pathlib import Path
from typing import List, Optional

from src.agent.guardrails import LegalGuardrail
from src.agent.llm_client import LocalLLMClient
from src.config import INCLUDE_PENDING_SOURCES, TOP_K_FINAL
from src.ingestion.contextual_chunker import ContextualChunker
from src.rag.corpus_loader import carregar_chunks_do_corpus
from src.observabilidade import atributos_do_trace, observacao, resumo_trechos
from src.models.schemas import (
    CausalGraphPath,
    ConsultantResponse,
    DocumentChunk,
    RetrievedChunk,
    TacoFoodNutrientRecord,
)
from src.retrieval.graph_engine import CausalKnowledgeGraphEngine
from src.retrieval.hybrid_retriever import HybridRetriever
from src.retrieval.taco_tool import TacoDeterministicTool


class NutritionConsultantBaseline:
    """
    Orquestrador do Consultor de Nutrição (RAG Híbrido Multi-Documento +
    Grafo de 4 Camadas PICO/GRADE + Ferramenta Determinística Tabela TACO +
    Guardrails da Lei Federal nº 8.234/91).
    """

    def __init__(
        self,
        guidelines_path: Optional[Path] = None,
        chunks: Optional[List[DocumentChunk]] = None,
        incluir_pendentes: bool = INCLUDE_PENDING_SOURCES,
        enable_ollama: bool = True,
        enable_taco_tool: bool = True,
        enable_graph_engine: bool = True,
        enable_rag: bool = True,
    ) -> None:
        self.chunker = ContextualChunker()
        # Base padrão: Trechos do corpus curado (ADR 0002), com o gate de aprovação.
        # `guidelines_path` mantém o modo legado sobre data/raw, usado só em testes antigos.
        if chunks is not None:
            self.chunks = chunks
        elif guidelines_path is not None:
            self.chunks = self.chunker.load_and_chunk_json(guidelines_path)
        else:
            self.chunks = carregar_chunks_do_corpus(incluir_pendentes=incluir_pendentes)
        self.incluir_pendentes = incluir_pendentes
        self.retriever = HybridRetriever(self.chunks)
        self.guardrail = LegalGuardrail()
        self.llm_client = LocalLLMClient(enable_ollama=enable_ollama)
        self.enable_taco_tool = enable_taco_tool
        self.enable_graph_engine = enable_graph_engine
        # Desligar a busca só faz sentido nos experimentos de ablação (linha de base "LLM puro").
        self.enable_rag = enable_rag
        self.taco_tool: Optional[TacoDeterministicTool] = (
            TacoDeterministicTool() if enable_taco_tool else None
        )
        self.graph_engine: Optional[CausalKnowledgeGraphEngine] = (
            CausalKnowledgeGraphEngine() if enable_graph_engine else None
        )

    def consult(self, user_query: str, top_k: int = TOP_K_FINAL) -> ConsultantResponse:
        # Com a observabilidade desligada (padrão), os blocos abaixo são no-ops.
        with atributos_do_trace(trace_name="consulta_nutricao", tags=["nutricao"]), observacao(
            "consult", input={"query": user_query, "top_k": top_k}
        ) as raiz:
            resposta = self._consultar(user_query, top_k)
            raiz.update(
                output={
                    "evidence_summary": resposta.evidence_summary,
                    "evidence_grade": resposta.evidence_grade,
                    "citations": resposta.citations,
                },
                metadata={
                    "model_used": resposta.model_used,
                    "retrieval_mode": resposta.retrieval_mode,
                    "guardrail_triggered": resposta.guardrail_triggered,
                    "intent_category": str(resposta.intent_category),
                },
            )
            raiz.score_trace(
                name="guardrail_lei_8234",
                value=1.0 if resposta.guardrail_triggered else 0.0,
                data_type="NUMERIC",
            )
            return resposta

    def _consultar(self, user_query: str, top_k: int) -> ConsultantResponse:
        # 1. Input Guardrail & Reframing (Conformidade com Lei nº 8.234/91)
        with observacao("guardrail_entrada", tipo="guardrail", input={"query": user_query}) as obs:
            assessment = self.guardrail.assess_and_reframe(user_query)
            obs.update(
                output={
                    "restrito_lei_8234": assessment.is_restricted_by_law_8234,
                    "intent_category": str(assessment.intent_category),
                    "query_reformulada": assessment.reframed_population_query,
                }
            )
        effective_query = assessment.reframed_population_query

        # 2. Recuperação Híbrida (BM25 + Vetorial Local + RRF + Reranker + Diversificação)
        search_query = (
            f"{effective_query} {user_query}"
            if assessment.is_restricted_by_law_8234
            else effective_query
        )
        retrieved: List[RetrievedChunk] = []
        if self.enable_rag:
            with observacao("retrieve", tipo="retriever", input={"query": search_query, "top_k": top_k}) as obs:
                retrieved = self.retriever.retrieve(search_query, top_k=top_k)
                obs.update(output=resumo_trechos(retrieved))

        # 3. Ferramenta Determinística da Tabela TACO (Passo 2)
        taco_records: List[TacoFoodNutrientRecord] = []
        taco_context_str = ""
        if self.taco_tool is not None:
            with observacao("taco", tipo="tool", input={"query": search_query}) as obs:
                taco_records, taco_context_str = self.taco_tool.auto_query_from_question(
                    search_query
                )
                obs.update(output=[rec.description for rec in taco_records])

        # 4. Travessia no Grafo de Conhecimento de 4 Camadas (Passo 3 - NetworkX)
        graph_paths: List[CausalGraphPath] = []
        graph_context_str = ""
        if self.graph_engine is not None:
            with observacao("grafo_causal", tipo="tool", input={"query": search_query}) as obs:
                graph_paths, graph_context_str = self.graph_engine.traverse_for_query(
                    search_query, max_paths=4
                )
                obs.update(output=graph_context_str)

        # 5. Síntese Baseada em Evidências (Modelo Local Ollama / Extrativo + Grafo + TACO)
        with observacao("sintese", input={"query": effective_query}) as obs:
            synthesis, model_used = self.llm_client.generate_structured_synthesis(
                query=effective_query,
                retrieved_chunks=retrieved,
                taco_context_str=taco_context_str,
                graph_context_str=graph_context_str,
            )
            obs.update(output=synthesis, metadata={"model_used": model_used})
            # Scores do trace para filtrar e montar painéis no Langfuse.
            obs.score_trace(name="modelo_usado", value=model_used, data_type="CATEGORICAL")
            obs.score_trace(
                name="sintese_extrativa",
                value=1.0 if model_used == "local_extractive_synthesis" else 0.0,
                data_type="NUMERIC",
            )

        # 6. Output Guardrail (Sanitização contra linguagem prescritiva individual)
        with observacao("guardrail_saida", tipo="guardrail") as obs:
            brutos = {
                campo: str(synthesis.get(campo, ""))
                for campo in ("evidence_summary", "physiological_mechanism", "protocol_findings")
            }
            sanitizados = {
                campo: self.guardrail.sanitize_output_text(texto)
                for campo, texto in brutos.items()
            }
            alterados = [campo for campo in brutos if brutos[campo] != sanitizados[campo]]
            obs.update(output={"campos_alterados": alterados})
            obs.score_trace(
                name="guardrail_saida_alterou", value=1.0 if alterados else 0.0, data_type="NUMERIC"
            )
        evidence_summary = sanitizados["evidence_summary"]
        physiological_mechanism = sanitizados["physiological_mechanism"]
        protocol_findings = sanitizados["protocol_findings"]

        citations: List[str] = []
        seen_docs = set()
        for item in retrieved:
            c = item.chunk
            cite_key = f"{c.doc_id}:{c.section_path}"
            if cite_key not in seen_docs:
                seen_docs.add(cite_key)
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
                    f"Seção: '{c.section_path}' (Evidência: {c.evidence_level}{meta_suffix})"
                )

        if graph_paths:
            citations.append(
                f"[KG_4LAYER_PICO_GRADE] Grafo de Conhecimento de 4 Camadas (NetworkX: {len(graph_paths)} cadeias causais Alimento ➔ Composto ➔ Mecanismo ➔ Desfecho)"
            )

        if taco_records:
            citations.append(
                "[TACO_4ED_UNICAMP] Tabela Brasileira de Composição de Alimentos (TACO 4ª Edição - NEPA/Unicamp & TBCA-USP) — Consulta Determinística por 100g"
            )

        food_list = list(synthesis.get("food_sources_or_compounds", []))
        for gp in graph_paths:
            if gp.food_node not in food_list and not gp.is_contraindicated_for_query:
                food_list.append(f"{gp.food_node} ({gp.compound_node})")
        for rec in taco_records:
            if rec.description not in food_list:
                food_list.append(rec.description)

        if taco_records and graph_paths:
            mode = "HYBRID_RAG_PLUS_GRAPH_AND_TACO"
        elif graph_paths:
            mode = "HYBRID_RAG_PLUS_GRAPH_TOOL"
        elif taco_records:
            mode = "HYBRID_RAG_PLUS_TACO_TOOL"
        else:
            mode = "HYBRID_RAG_BASELINE"

        return ConsultantResponse(
            original_query=user_query,
            effective_query=effective_query,
            guardrail_triggered=assessment.is_restricted_by_law_8234,
            intent_category=assessment.intent_category,
            legal_compliance_notice=assessment.legal_notice_required,
            evidence_summary=evidence_summary,
            physiological_mechanism=physiological_mechanism,
            protocol_findings=protocol_findings,
            food_sources_or_compounds=food_list,
            taco_records=taco_records,
            graph_paths=graph_paths,
            evidence_grade=str(synthesis.get("evidence_grade", "N/A")),
            citations=citations,
            retrieved_chunks=retrieved,
            model_used=model_used,
            retrieval_mode=mode,
        )
