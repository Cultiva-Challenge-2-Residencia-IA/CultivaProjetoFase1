from typing import Dict, List, Literal, Optional
from pydantic import BaseModel, Field


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
    model_used: str = "local"
    retrieval_mode: Literal[
        "HYBRID_RAG_BASELINE",
        "HYBRID_RAG_PLUS_TACO_TOOL",
        "HYBRID_RAG_PLUS_GRAPH_TOOL",
        "HYBRID_RAG_PLUS_GRAPH_AND_TACO",
    ] = "HYBRID_RAG_BASELINE"
