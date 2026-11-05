from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class Trecho(BaseModel):
    """
    Esquema canônico e único do Trecho (chunk) compartilhado entre a camada de Corpus e o Retriever.
    Garante rastreabilidade rigorosa até o PDF original, auditoria de licenças e governança de aprovação.
    Campos mínimos obrigatórios: id, fonte_id, pagina_pdf, secao, texto, licenca, approval_status.
    """
    id: str = Field(
        ...,
        description="Identificador único, estável e determinístico do trecho (ex.: guia-2014-p025-s02).",
    )
    fonte_id: str = Field(
        ...,
        description="Identificador da fonte no corpus/manifest.yaml (ex.: guia-alimentar-populacao-brasileira-2014).",
    )
    pagina_pdf: int = Field(
        ...,
        ge=1,
        description="Número da página física no PDF original de onde o trecho foi extraído (iniciando em 1).",
    )
    secao: str = Field(
        ...,
        description="Hierarquia ou título da seção/capítulo do documento onde o trecho está contido.",
    )
    texto: str = Field(
        ...,
        description="Conteúdo textual fidedigno do trecho extraído da fonte.",
    )
    licenca: str = Field(
        ...,
        description="Identificador ou termos da licença legal verificada da fonte (ex.: CC-BY-NC-SA-4.0).",
    )
    approval_status: str = Field(
        ...,
        description="Status de aprovação técnica/científica da fonte/trecho: 'aprovado', 'pendente', 'bloqueado' ou 'rejeitado'.",
    )

    # Campos complementares opcionais de enriquecimento e compatibilidade:
    titulo_fonte: Optional[str] = Field(default=None, description="Título legível da obra original.")
    ano_publicacao: Optional[int] = Field(default=None, description="Ano de publicação da fonte.")
    instituicao: Optional[str] = Field(default=None, description="Instituição responsável pela publicação.")
    nivel_evidencia: Optional[str] = Field(default=None, description="Grau de evidência científica (ex.: GRADE_A, GUIDELINE_CONSENSUS).")
    contexto_adicional: Optional[str] = Field(default=None, description="Cabeçalho contextual de suporte à indexação/busca.")

    def to_document_chunk(self) -> "DocumentChunk":
        """Converte Trecho para o modelo legado DocumentChunk mantendo interoperabilidade."""
        contextualized = self.contexto_adicional or f"[{self.secao} | p.{self.pagina_pdf}]\n{self.texto}"
        evidence = self.nivel_evidencia if self.nivel_evidencia in ["GRADE_A", "GRADE_B", "GRADE_C", "GUIDELINE_CONSENSUS"] else "GUIDELINE_CONSENSUS"
        return DocumentChunk(
            chunk_id=self.id,
            doc_id=self.fonte_id,
            title=self.titulo_fonte or self.secao,
            source_organization=self.instituicao or "Ministério da Saúde",
            publication_year=self.ano_publicacao or 2014,
            clinical_domain="nutricao_populacional",
            evidence_level=evidence,
            section_path=self.secao,
            raw_text=self.texto,
            contextualized_text=contextualized,
        )

    @classmethod
    def from_document_chunk(
        cls,
        chunk: "DocumentChunk",
        licenca: str = "CC-BY-NC-SA-4.0",
        approval_status: str = "aprovado",
        pagina_pdf: int = 1,
    ) -> "Trecho":
        """Cria um Trecho a partir de um DocumentChunk legado."""
        return cls(
            id=chunk.chunk_id,
            fonte_id=chunk.doc_id,
            pagina_pdf=pagina_pdf,
            secao=chunk.section_path,
            texto=chunk.raw_text,
            licenca=licenca,
            approval_status=approval_status,
            titulo_fonte=chunk.title,
            ano_publicacao=chunk.publication_year,
            instituicao=chunk.source_organization,
            nivel_evidencia=chunk.evidence_level,
            contexto_adicional=chunk.contextualized_text,
        )


class TrechoRecuperado(BaseModel):
    """
    Resultado canônico retornado pela interface do Retriever.
    Agrupa o Trecho e os scores calculados no processo de busca.
    """
    trecho: Trecho = Field(..., description="Trecho documental recuperado.")
    score: float = Field(..., description="Pontuação composta final ou relevância calculada para o trecho.")
    score_detalhes: Dict[str, float] = Field(
        default_factory=dict,
        description="Detalhamento das pontuações dos componentes (ex.: bm25, vector, rrf, rerank).",
    )
    rank: Optional[int] = Field(default=None, description="Posição ordinal do trecho no ranking (1-based).")

    def to_retrieved_chunk(self) -> "RetrievedChunk":
        """Converte para RetrievedChunk legado mantendo compatibilidade."""
        return RetrievedChunk(
            chunk=self.trecho.to_document_chunk(),
            bm25_score=self.score_detalhes.get("bm25_score", 0.0),
            vector_score=self.score_detalhes.get("vector_score", 0.0),
            rrf_score=self.score_detalhes.get("rrf_score", self.score),
            rerank_score=self.score_detalhes.get("rerank_score", self.score),
        )

    @classmethod
    def from_retrieved_chunk(
        cls,
        rc: "RetrievedChunk",
        licenca: str = "CC-BY-NC-SA-4.0",
        approval_status: str = "aprovado",
        pagina_pdf: int = 1,
        rank: Optional[int] = None,
    ) -> "TrechoRecuperado":
        """Cria TrechoRecuperado a partir de um RetrievedChunk legado."""
        trecho = Trecho.from_document_chunk(
            rc.chunk,
            licenca=licenca,
            approval_status=approval_status,
            pagina_pdf=pagina_pdf,
        )
        scores = {
            "bm25_score": rc.bm25_score,
            "vector_score": rc.vector_score,
            "rrf_score": rc.rrf_score,
            "rerank_score": rc.rerank_score,
        }
        final_score = rc.rerank_score if rc.rerank_score > 0 else rc.rrf_score
        return cls(
            trecho=trecho,
            score=final_score,
            score_detalhes=scores,
            rank=rank,
        )


class SinaisFluxo(BaseModel):
    """
    Sinais operacionais emitidos pelo fluxo do agente de Nutrição para leitura e auditoria da camada de avaliação (eval).
    Permite validar conformidade legal (Lei 8.234/91), segurança clínica e reconhecimento de limites (RN01-RN04, RN16-RN17, RF-IA01, RF-IA02).
    Sinais mínimos do fluxo: risco, recusa, redirecionamento, nao_sei.
    """
    risco: bool = Field(
        default=False,
        description="Indica se foram detectadas condições clínicas de risco ou contraindicações fisiológicas na consulta/resposta.",
    )
    risco_detalhes: List[str] = Field(
        default_factory=list,
        description="Lista de tags ou condições de risco identificadas (ex.: restrição renal de potássio).",
    )
    recusa: bool = Field(
        default=False,
        description="Indica se o fluxo recusou atender a solicitação por violar vedações legais (Lei 8.234/91: prescrição de cardápio, dose ou diagnóstico).",
    )
    recusa_motivo: Optional[str] = Field(
        default=None,
        description="Descrição da regra de negócio ou artigo de lei que motivou a recusa.",
    )
    redirecionamento: bool = Field(
        default=False,
        description="Indica se a consulta foi reenquadrada para abordagem populacional/educativa e/ou orientou busca por profissional de saúde.",
    )
    redirecionamento_consulta: Optional[str] = Field(
        default=None,
        description="Texto da consulta reenquadrada com foco em evidências populacionais e diretrizes.",
    )
    redirecionamento_aviso: Optional[str] = Field(
        default=None,
        description="Texto da nota de conformidade legal ou orientação de consulta profissional.",
    )
    nao_sei: bool = Field(
        default=False,
        description="Indica abstenção deliberada por ausência ou insuficiência de evidência no corpus aprovado (RN04/RN16/RN17/RF-IA01).",
    )
    nao_sei_motivo: Optional[str] = Field(
        default=None,
        description="Explicação da ausência de evidência confiável ou baixa pontuação de recuperação.",
    )


class DocumentSectionInput(BaseModel):
    section_path: str
    text: str


class GuidelineDocumentInput(BaseModel):
    doc_id: str
    title: str
    source_organization: str
    publication_year: int
    clinical_domain: str
    evidence_level: Literal["GRADE_A", "GRADE_B", "GRADE_C", "GUIDELINE_CONSENSUS"]
    sections: List[DocumentSectionInput]


class DocumentChunk(BaseModel):
    chunk_id: str
    doc_id: str
    title: str
    source_organization: str
    publication_year: int
    clinical_domain: str
    evidence_level: Literal["GRADE_A", "GRADE_B", "GRADE_C", "GUIDELINE_CONSENSUS"]
    section_path: str
    raw_text: str
    contextualized_text: str


class RetrievedChunk(BaseModel):
    chunk: DocumentChunk
    bm25_rank: Optional[int] = None
    bm25_score: float = 0.0
    vector_rank: Optional[int] = None
    vector_score: float = 0.0
    rrf_score: float = 0.0
    rerank_score: float = 0.0


class GuardrailAssessment(BaseModel):
    intent_category: Literal[
        "SAFE_EVIDENCE_QUERY",
        "RESTRICTED_DIET_PRESCRIPTION",
        "RESTRICTED_CLINICAL_DIAGNOSIS",
        "RESTRICTED_SUPPLEMENT_POSOLOGY",
    ]
    is_restricted_by_law_8234: bool
    triggered_rules: List[str] = Field(default_factory=list)
    reframed_population_query: str = Field(
        description="Pergunta reescrita com foco em evidências científicas populacionais e mecanismos fisiológicos."
    )
    legal_notice_required: Optional[str] = None


class TacoFoodNutrientRecord(BaseModel):
    food_id: int
    description: str
    category: str
    energy_kcal: Optional[float] = None
    protein_g: Optional[float] = None
    fiber_g: Optional[float] = None
    nutrients_per_100g: Dict[str, float] = Field(default_factory=dict)
    source: str = "Tabela TACO 4ª Ed. (Unicamp) / TBCA-USP"


class CausalGraphPath(BaseModel):
    path_id: str
    food_node: str
    compound_node: str
    compound_concentration_info: str = ""
    mechanism_node: str
    outcome_node: str
    effect_direction: Literal["DECREASES", "INCREASES", "MODULATES", "INHIBITS_ABSORPTION"]
    relationship_nature: Literal[
        "CAUSAL_ECR_META_ANALYSIS",
        "CLINICAL_GUIDELINE_CONSENSUS",
        "IN_VITRO_OR_LOW_BIOAVAILABILITY_ALONE",
    ]
    evidence_grade: Literal["GRADE_A", "GRADE_B", "GRADE_C", "GUIDELINE_CONSENSUS"]
    studied_protocol: str
    contraindications: List[str] = Field(default_factory=list)
    is_contraindicated_for_query: bool = False
    source_reference: str


class ConsultantResponse(BaseModel):
    original_query: str
    effective_query: str
    guardrail_triggered: bool
    intent_category: str
    legal_compliance_notice: Optional[str] = None
    evidence_summary: str
    physiological_mechanism: str
    protocol_findings: str
    food_sources_or_compounds: List[str] = Field(default_factory=list)
    taco_records: List[TacoFoodNutrientRecord] = Field(default_factory=list)
    graph_paths: List[CausalGraphPath] = Field(default_factory=list)
    evidence_grade: str
    citations: List[str] = Field(default_factory=list)
    retrieved_chunks: List[RetrievedChunk] = Field(default_factory=list)
    trechos_recuperados: List[TrechoRecuperado] = Field(default_factory=list)
    sinais: Optional[SinaisFluxo] = None
    model_used: str = "local"
    retrieval_mode: Literal[
        "HYBRID_RAG_BASELINE",
        "HYBRID_RAG_PLUS_TACO_TOOL",
        "HYBRID_RAG_PLUS_GRAPH_TOOL",
        "HYBRID_RAG_PLUS_GRAPH_AND_TACO",
    ] = "HYBRID_RAG_BASELINE"
