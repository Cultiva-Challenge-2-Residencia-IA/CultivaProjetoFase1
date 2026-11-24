import hashlib
import inspect
from contextvars import ContextVar
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional

from src.agent.guardrails import LegalGuardrail
from src.agent.llm_client import LocalLLMClient
from src.agent.llm_client import SYSTEM_PROMPT_CONSULTANT, SYSTEM_PROMPT_SEM_CONTEXTO
from src.agent.traceability import corpus_version_do_indice, new_response_id, passages_fingerprint
from src.config import (
    FILTRO_RELEVANCIA_LIMIAR,
    FILTRO_RELEVANCIA_NUTRICAO,
    FILTRO_RELEVANCIA_SAUDE_FISICA,
    INCLUDE_PENDING_SOURCES,
    OLLAMA_BASE_URL,
    REFORMULACAO_LLM,
    RERANKER_CANDIDATOS,
    RERANKER_MODELO,
    RERANKER_NUTRICAO,
    RERANKER_SAUDE_FISICA,
    RISCO_LLM_LIMIAR,
    RISCO_LLM_MODELO,
    RISCO_LLM_TIMEOUT,
    TOP_K_FINAL,
)
from src.guardrails.risco import detectar_risco
from src.guardrails.risco.classificador_llm import ClassificadorRiscoLLM
from src.ingestion.contextual_chunker import ContextualChunker
from src.rag.corpus_loader import carregar_chunks_do_corpus
from src.observabilidade import atributos_do_trace, id_do_trace, observacao, scores_da_resposta
from src.models.schemas import (
    ConsultantResponse,
    DocumentChunk,
)
from src.retrieval.graph_engine import CausalKnowledgeGraphEngine
from src.retrieval.hybrid_retriever import HybridRetriever
from src.retrieval.reranker_cruzado import RerankerCruzado
from src.retrieval.taco_tool import TacoDeterministicTool

if TYPE_CHECKING:
    from src.orquestrador.reescrita import Mensagem


# Versão do prompt (RNF08): hash do prompt de sistema e do template da pergunta enviada ao LLM.
# response_id da consulta em andamento: `consult()` o gera antes de abrir o trace, para o id do trace
# no Langfuse sair dele (`id_do_trace`) e o feedback de resposta incorreta achar o trace certo.
_RESPONSE_ID_ATUAL: ContextVar[Optional[str]] = ContextVar("response_id_atual", default=None)

PROMPT_VERSION = hashlib.sha256(
    (SYSTEM_PROMPT_CONSULTANT + inspect.getsource(LocalLLMClient._build_user_prompt)).encode("utf-8")
).hexdigest()
# Linha de base "LLM puro" da ablação: outro prompt de sistema, sem Trechos no prompt do usuário.
PROMPT_VERSION_SEM_CONTEXTO = hashlib.sha256(
    (SYSTEM_PROMPT_SEM_CONTEXTO + inspect.getsource(LocalLLMClient.generate_structured_synthesis)).encode("utf-8")
).hexdigest()


class NutritionConsultantBaseline:
    """
    Orquestrador do Consultor de Nutrição (RAG Híbrido Multi-Documento +
    Grafo de 4 Camadas PICO/GRADE + Ferramenta Determinística Tabela TACO +
    Guardrails da Lei Federal nº 8.234/91).
    """

    area = "nutricao"

    def __init__(
        self,
        guidelines_path: Optional[Path] = None,
        chunks: Optional[List[DocumentChunk]] = None,
        incluir_pendentes: bool = INCLUDE_PENDING_SOURCES,
        enable_ollama: bool = True,
        enable_taco_tool: bool = True,
        enable_graph_engine: bool = True,
        enable_rag: bool = True,
        risco_llm: Optional[ClassificadorRiscoLLM] = None,
        com_portao_de_risco: bool = True,
        reranker_na_busca: Optional[bool] = None,
        filtro_relevancia: Optional[bool] = None,
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
        # Relevância da busca (issue #105): reranker cross-encoder ligado por área e filtro antes da
        # síntese, com os padrões de src/config.py. O modelo só é carregado na primeira pergunta.
        if reranker_na_busca is None:
            reranker_na_busca = RERANKER_SAUDE_FISICA if self.area == "saude_fisica" else RERANKER_NUTRICAO
        if filtro_relevancia is None:
            filtro_relevancia = (
                FILTRO_RELEVANCIA_SAUDE_FISICA if self.area == "saude_fisica" else FILTRO_RELEVANCIA_NUTRICAO
            )
        reranker = RerankerCruzado(RERANKER_MODELO) if reranker_na_busca or filtro_relevancia else None
        self.retriever = HybridRetriever(
            self.chunks,
            reranker=reranker if reranker_na_busca else None,
            candidatos_reranker=RERANKER_CANDIDATOS,
        )
        self.filtro_reranker = reranker if filtro_relevancia else None
        self.filtro_limiar = FILTRO_RELEVANCIA_LIMIAR
        # Reformulação da busca sem Trecho relevante: só com o Ollama local (ADR 0004).
        self.reformulacao_llm = None
        if filtro_relevancia and enable_ollama and REFORMULACAO_LLM:
            from src.agent.llm_json import ClienteJsonOllama

            self.reformulacao_llm = ClienteJsonOllama("reformulacao_busca", num_predict=256)
        self.guardrail = LegalGuardrail()
        self.llm_client = LocalLLMClient(enable_ollama=enable_ollama)
        self.enable_taco_tool = enable_taco_tool
        self.enable_graph_engine = enable_graph_engine
        # Desligar a busca só faz sentido nos experimentos de ablação (linha de base "LLM puro").
        self.enable_rag = enable_rag
        self.taco_tool: Optional[TacoDeterministicTool] = (
            TacoDeterministicTool() if enable_taco_tool else None
        )
        # Linha de base "LLM puro" da ablação: só quando as três fontes de contexto estão
        # desligadas por configuração. Não é modo do produto.
        self.modo_llm_puro = not enable_rag and not enable_taco_tool and not enable_graph_engine
        self.graph_engine: Optional[CausalKnowledgeGraphEngine] = (
            CausalKnowledgeGraphEngine() if enable_graph_engine else None
        )
        # Camada semântica do risco (issue #48): só com Ollama habilitado e modelo configurado.
        # Agente usado só pelo Chat (Saúde Física) não tem portão próprio: o Chat aplica os portões.
        if risco_llm is None and enable_ollama and RISCO_LLM_MODELO and com_portao_de_risco:
            risco_llm = ClassificadorRiscoLLM(RISCO_LLM_MODELO, base_url=OLLAMA_BASE_URL,
                                              timeout=RISCO_LLM_TIMEOUT, limiar=RISCO_LLM_LIMIAR)
        self.risco_llm = risco_llm
        if self.risco_llm is not None:
            # Carrega o modelo na memória já na inicialização, para a primeira pergunta caber no RNF29.
            ClassificadorRiscoLLM(self.risco_llm.modelo, base_url=self.risco_llm.base_url,
                                  timeout=60.0, modo=self.risco_llm.modo).classificar("Olá")

    def _rastreabilidade(self, chunks: List[DocumentChunk], model_used: str) -> dict:
        """Campos de rastreabilidade (#11, RNF08) de qualquer resposta, inclusive as fixas.

        Não grava nada: a persistência fica na API (`/consult`), para testes, benchmark e
        demonstração não escreverem no banco.
        """
        fontes_version, trechos_usados = passages_fingerprint(chunks)
        return {
            "response_id": _RESPONSE_ID_ATUAL.get() or new_response_id(),
            "corpus_version": self.corpus_version,
            "prompt_version": (
                PROMPT_VERSION_SEM_CONTEXTO if getattr(self, "modo_llm_puro", False)
                else getattr(self, "prompt_version", PROMPT_VERSION)
            ),
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
                risco_llm=getattr(self, "risco_llm", None),
            )
            self._grafo_compilado = grafo
        return grafo

    def responder(self, pergunta: str, top_k: int, consultas_extras: List[str],
                  historico: List["Mensagem"]) -> ConsultantResponse:
        """Responde como Agente de área do Chat (issue #99): só o subgrafo, sem os portões, que o
        Chat já aplicou. `historico` é o da área deste agente (RF-IA09)."""
        subgrafo = getattr(self, "_subgrafo_compilado", None)
        if subgrafo is None:
            from src.agents.nutricao.grafo import construir_subgrafo

            subgrafo = self._subgrafo_compilado = construir_subgrafo(self)
        texto = "\n".join(f"{'Usuário' if m.papel == 'usuario' else 'Assistente'}: {m.texto}" for m in historico)
        estado = subgrafo.invoke({"pergunta": pergunta, "top_k": top_k,
                                  "consultas_extras": list(consultas_extras), "historico": texto})
        return estado["resposta"]

    def consult(self, user_query: str, top_k: int = TOP_K_FINAL) -> ConsultantResponse:
        """Responde pela orquestração em LangGraph: portões de risco e de prompt injection no grafo
        principal (`src/orquestrador/grafo.py`) e o fluxo de Nutrição no subgrafo
        (`src/agents/nutricao/grafo.py`).

        Com a observabilidade desligada (padrão), os blocos de observação são no-ops. Ligada, todo
        texto passa pela máscara de dados pessoais no SDK (src/observabilidade.py, ADR 0003). A
        observação raiz fica fora do grafo, e não no callback do LangGraph, porque a entrada só pode
        ser decidida depois do portão de risco: mensagem que ele detecta não é registrada, nem
        mascarada, e o trace guarda só as categorias. A entrada inicial usa só o léxico, que deixa
        passar a maioria das frases novas (recall de 0,133 no holdout); quando a camada LLM (#48)
        detecta o risco, a entrada é sobrescrita pelas categorias antes de a observação fechar.
        """
        risco = detectar_risco(user_query)
        entrada = (
            {"risco_categorias": risco.categorias, "top_k": top_k}
            if risco.risco
            else {"query": user_query, "top_k": top_k}
        )
        response_id = new_response_id()
        marcador = _RESPONSE_ID_ATUAL.set(response_id)
        try:
            return self._consultar_com_trace(user_query, top_k, entrada, response_id, risco.risco)
        finally:
            _RESPONSE_ID_ATUAL.reset(marcador)

    def _consultar_com_trace(
        self, user_query: str, top_k: int, entrada: dict, response_id: str, risco_lexico: bool
    ) -> ConsultantResponse:
        with atributos_do_trace(
            trace_name="consulta_nutricao",
            tags=["nutricao"],
            version=(
                PROMPT_VERSION_SEM_CONTEXTO if getattr(self, "modo_llm_puro", False) else PROMPT_VERSION
            ),
            metadata={"corpus_version": str(self.corpus_version)},
        ), observacao("consult", input=entrada, trace_id=id_do_trace(response_id)) as raiz:
            estado = self._grafo().invoke({"pergunta": user_query, "top_k": top_k})
            resposta = estado["resposta"]
            if resposta.risk_triggered:
                # Risco detectado só pelo LLM (o léxico não viu): a pergunta sai do trace, ficam as categorias.
                if not risco_lexico:
                    raiz.update(input={"risco_categorias": resposta.risk_categories, "top_k": top_k})
            else:
                resposta.risk_llm_status = estado.get("risco_llm_status")
            raiz.update(
                output={
                    "evidence_summary": resposta.evidence_summary,
                    "evidence_grade": resposta.evidence_grade,
                    "citations": resposta.citations,
                },
                metadata={
                    "response_id": resposta.response_id,
                    "model_used": resposta.model_used,
                    "retrieval_mode": resposta.retrieval_mode,
                    "guardrail_triggered": resposta.guardrail_triggered,
                    "intent_category": str(resposta.intent_category),
                    "fundamentacao_status": resposta.fundamentacao_status,
                    "corpus_version": resposta.corpus_version,
                    "prompt_version": resposta.prompt_version,
                    "model_version": resposta.model_version,
                    "fontes_version": resposta.fontes_version,
                },
            )
            for nome, valor, tipo in scores_da_resposta(resposta):
                raiz.score_trace(name=nome, value=valor, data_type=tipo)
            return resposta
