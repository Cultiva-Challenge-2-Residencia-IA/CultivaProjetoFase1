from pathlib import Path
from typing import List, Optional

from src.agent.guardrails import LAW_8234_COMPLIANCE_NOTICE, LegalGuardrail
from src.agent.llm_client import LocalLLMClient
from src.config import (
    ABSTENCAO_LIMIAR_COSSENO,
    INCLUDE_PENDING_SOURCES,
    OLLAMA_BASE_URL,
    RISCO_LLM_MODELO,
    RISCO_LLM_TIMEOUT,
    TOP_K_FINAL,
)
from src.rag.abstencao import MENSAGEM_NAO_SEI, fora_do_dominio
from src.guardrails.injection import MENSAGEM_INJECAO, has_prompt_injection
from src.guardrails.risco import MENSAGEM_ACOLHIMENTO, detectar_risco
from src.guardrails.risco.classificador_llm import ClassificadorRiscoLLM
from src.ingestion.contextual_chunker import ContextualChunker
from src.rag.corpus_loader import carregar_chunks_do_corpus
from src.models.schemas import (
    CausalGraphPath,
    ConsultantResponse,
    DocumentChunk,
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
        risco_llm: Optional[ClassificadorRiscoLLM] = None,
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
        self.taco_tool: Optional[TacoDeterministicTool] = (
            TacoDeterministicTool() if enable_taco_tool else None
        )
        self.graph_engine: Optional[CausalKnowledgeGraphEngine] = (
            CausalKnowledgeGraphEngine() if enable_graph_engine else None
        )
        # Camada semântica do risco (issue #48): só com Ollama habilitado e modelo configurado.
        if risco_llm is None and enable_ollama and RISCO_LLM_MODELO:
            risco_llm = ClassificadorRiscoLLM(RISCO_LLM_MODELO, base_url=OLLAMA_BASE_URL,
                                              timeout=RISCO_LLM_TIMEOUT)
        self.risco_llm = risco_llm
        if self.risco_llm is not None:
            # Carrega o modelo na memória já na inicialização, para a primeira pergunta caber no RNF29.
            ClassificadorRiscoLLM(self.risco_llm.modelo, base_url=self.risco_llm.base_url,
                                  timeout=60.0, modo=self.risco_llm.modo).classificar("Olá")

    def _resposta_fixa(self, user_query: str, mensagem: str, **campos) -> ConsultantResponse:
        """Resposta sem LLM (risco, prompt injection e "não sei")."""
        return ConsultantResponse(
            original_query=user_query,
            effective_query=user_query,
            evidence_summary=mensagem,
            physiological_mechanism="",
            protocol_findings="",
            evidence_grade="N/A",
            model_used="mensagem_fixa",
            **campos,
        )

    def consult(self, user_query: str, top_k: int = TOP_K_FINAL) -> ConsultantResponse:
        # 0. Risco antes de tudo (RF-IA03, RNF29): interrompe o fluxo com mensagem fixa.
        # O léxico é o piso; o LLM local só é consultado quando ele não aciona (issue #48).
        risco = detectar_risco(user_query)
        categorias, camada, status_llm = risco.categorias, "lexico", None
        risco_llm = getattr(self, "risco_llm", None)
        if not risco.risco and risco_llm is not None:
            resultado = risco_llm.classificar(user_query)
            status_llm = "falhou" if resultado is None else "ok"
            if resultado is not None and resultado.risco:
                categorias, camada = resultado.categorias, "llm"
        if categorias:
            return self._resposta_fixa(
                user_query,
                MENSAGEM_ACOLHIMENTO,
                guardrail_triggered=False,
                intent_category="RISK_SUPPORT",
                risk_triggered=True,
                risk_categories=categorias,
                risk_layer=camada,
                risk_llm_status=status_llm,
                retrieval_mode="RISK_FIXED_MESSAGE",
            )
        resposta = self._consultar_sem_risco(user_query, top_k)
        resposta.risk_llm_status = status_llm
        return resposta

    def _consultar_sem_risco(self, user_query: str, top_k: int) -> ConsultantResponse:
        # 0.1 Prompt injection na pergunta (RNF04): recusa fixa, sem repassar o pedido ao LLM.
        if has_prompt_injection(user_query):
            return self._resposta_fixa(
                user_query,
                MENSAGEM_INJECAO,
                guardrail_triggered=True,
                intent_category="PROMPT_INJECTION_BLOCKED",
                legal_compliance_notice=LAW_8234_COMPLIANCE_NOTICE,
                prompt_injection_detected=True,
                retrieval_mode="PROMPT_INJECTION_FIXED_MESSAGE",
            )

        # 1. Input Guardrail & Reframing (Conformidade com Lei nº 8.234/91)
        assessment = self.guardrail.assess_and_reframe(user_query)
        effective_query = assessment.reframed_population_query

        # 2. Recuperação Híbrida (BM25 + Vetorial Local + RRF + Reranker + Diversificação)
        search_query = (
            f"{effective_query} {user_query}"
            if assessment.is_restricted_by_law_8234
            else effective_query
        )
        retrieved = self.retriever.retrieve(search_query, top_k=top_k)

        # 3. Ferramenta Determinística da Tabela TACO (Passo 2)
        taco_records: List[TacoFoodNutrientRecord] = []
        taco_context_str = ""
        if self.taco_tool is not None:
            taco_records, taco_context_str = self.taco_tool.auto_query_from_question(
                search_query
            )

        # 4. Travessia no Grafo de Conhecimento de 4 Camadas (Passo 3 - NetworkX)
        graph_paths: List[CausalGraphPath] = []
        graph_context_str = ""
        if self.graph_engine is not None:
            graph_paths, graph_context_str = self.graph_engine.traverse_for_query(
                search_query, max_paths=4
            )

        # 4.1 "Não sei" (RF-IA01): pergunta fora do domínio de Nutrição (cosseno baixo e nenhum termo
        #     de Nutrição) recebe resposta fixa, sem LLM. Se o grafo ou a TACO tiverem resultado,
        #     responde só com eles. Dentro do domínio, o fluxo segue com os Trechos que a busca achou.
        similaridade = round(self.retriever.similaridade_maxima(search_query), 4)
        if fora_do_dominio(user_query, similaridade, ABSTENCAO_LIMIAR_COSSENO):
            if not taco_records and not graph_paths:
                return self._resposta_fixa(
                    user_query,
                    MENSAGEM_NAO_SEI,
                    guardrail_triggered=assessment.is_restricted_by_law_8234,
                    intent_category="NO_EVIDENCE",
                    legal_compliance_notice=assessment.legal_notice_required,
                    abstencao=True,
                    similaridade_maxima=similaridade,
                    retrieval_mode="ABSTENTION_FIXED_MESSAGE",
                )
            retrieved = []

        # 5. Síntese Baseada em Evidências (Modelo Local Ollama / Extrativo + Grafo + TACO)
        synthesis, model_used = self.llm_client.generate_structured_synthesis(
            query=effective_query,
            retrieved_chunks=retrieved,
            taco_context_str=taco_context_str,
            graph_context_str=graph_context_str,
        )

        # 6. Output Guardrail (Sanitização contra linguagem prescritiva individual)
        evidence_summary = self.guardrail.sanitize_output_text(
            str(synthesis.get("evidence_summary", ""))
        )
        physiological_mechanism = self.guardrail.sanitize_output_text(
            str(synthesis.get("physiological_mechanism", ""))
        )
        protocol_findings = self.guardrail.sanitize_output_text(
            str(synthesis.get("protocol_findings", ""))
        )

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
            similaridade_maxima=similaridade,
        )
