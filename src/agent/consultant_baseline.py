import hashlib
import inspect
from pathlib import Path
from typing import List, Optional

from src.agent.guardrails import LegalGuardrail
from src.agent.llm_client import LocalLLMClient
from src.agent.llm_client import SYSTEM_PROMPT_CONSULTANT
from src.agent.traceability import corpus_version_do_indice, new_response_id, passages_fingerprint
from src.config import INCLUDE_PENDING_SOURCES, TOP_K_FINAL
from src.ingestion.contextual_chunker import ContextualChunker
from src.rag.corpus_loader import carregar_chunks_do_corpus
from src.models.schemas import (
    ConsultantResponse,
    DocumentChunk,
)
from src.retrieval.graph_engine import CausalKnowledgeGraphEngine
from src.retrieval.hybrid_retriever import HybridRetriever
from src.retrieval.taco_tool import TacoDeterministicTool


# Versão do prompt (RNF08): hash do prompt de sistema e do template da pergunta enviada ao LLM.
PROMPT_VERSION = hashlib.sha256(
    (SYSTEM_PROMPT_CONSULTANT + inspect.getsource(LocalLLMClient._build_user_prompt)).encode("utf-8")
).hexdigest()


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
        # Rastreabilidade (#11): o corpus não muda enquanto o consultor existe, então a versão é
        # calculada uma vez aqui, e não a cada pergunta.
        self.corpus_version = corpus_version_do_indice(self.chunks)
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

    def _rastreabilidade(self, chunks: List[DocumentChunk], model_used: str) -> dict:
        """Campos de rastreabilidade (#11, RNF08) de qualquer resposta, inclusive as fixas.

        Não grava nada: a persistência fica na API (`/consult`), para testes, benchmark e
        demonstração não escreverem no banco.
        """
        fontes_version, trechos_usados = passages_fingerprint(chunks)
        return {
            "response_id": new_response_id(),
            "corpus_version": self.corpus_version,
            "prompt_version": PROMPT_VERSION,
            "model_version": model_used,
            "fontes_version": fontes_version,
            "trechos_usados": trechos_usados,
        }

    def _resposta_fixa(self, user_query: str, mensagem: str, **campos) -> ConsultantResponse:
        """Resposta sem LLM (risco, prompt injection e "não sei"), também rastreável (RF-IA15)."""
        return ConsultantResponse(
            original_query=user_query,
            effective_query=user_query,
            evidence_summary=mensagem,
            physiological_mechanism="",
            protocol_findings="",
            evidence_grade="N/A",
            model_used="mensagem_fixa",
            **self._rastreabilidade([], "mensagem_fixa"),
            **campos,
        )

    def _grafo(self):
        """Grafo do orquestrador (issue #76), compilado na primeira chamada e reaproveitado."""
        grafo = getattr(self, "_grafo_compilado", None)
        if grafo is None:
            # Import tardio: src.agents.nutricao reexporta esta classe.
            from src.agents.nutricao.grafo import construir_subgrafo
            from src.orquestrador.grafo import construir_grafo

            grafo = construir_grafo(
                agentes={"nutricao": construir_subgrafo(self)},
                resposta_fixa=self._resposta_fixa,
                agente_padrao="nutricao",
            )
            self._grafo_compilado = grafo
        return grafo

    def consult(self, user_query: str, top_k: int = TOP_K_FINAL) -> ConsultantResponse:
        """Responde pela orquestração em LangGraph: portões de risco e de prompt injection no grafo
        principal (`src/orquestrador/grafo.py`) e o fluxo de Nutrição no subgrafo
        (`src/agents/nutricao/grafo.py`)."""
        return self._grafo().invoke({"pergunta": user_query, "top_k": top_k})["resposta"]
