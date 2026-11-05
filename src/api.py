import sys
from typing import Optional
from fastapi import FastAPI
from pydantic import BaseModel, Field

from src.agent.consultant_baseline import NutritionConsultantBaseline
from src.config import TOP_K_FINAL
from src.models.schemas import ConsultantResponse

app = FastAPI(
    title="Consultor Científico de Nutrição Baseado em Evidências (Fase 1 - Baseline RAG Híbrido)",
    description=(
        "Sistema de apoio informativo baseado em diretrizes científicas e literatura (RAG Híbrido: BM25 + "
        "Vetorial Local + RRF + Reranker), em conformidade com a Lei Federal nº 8.234/1991 (CFN)."
    ),
    version="0.1.0",
)

_consultant_instance: Optional[NutritionConsultantBaseline] = None


def get_consultant() -> NutritionConsultantBaseline:
    global _consultant_instance
    if _consultant_instance is None:
        _consultant_instance = NutritionConsultantBaseline(enable_ollama=True)
    return _consultant_instance


class ConsultRequest(BaseModel):
    query: str = Field(..., min_length=3, description="Dúvida geral de consulta nutricional")
    top_k: int = Field(default=TOP_K_FINAL, ge=1, le=10)


@app.get("/health")
def health_check() -> dict:
    consultant = get_consultant()
    graph_stats = (
        consultant.graph_engine.get_graph_stats()
        if consultant.graph_engine is not None
        else {}
    )
    return {
        "status": "ok",
        "phase": "PHASE_2_HYBRID_RAG_PLUS_4LAYER_GRAPH_AND_TACO",
        "indexed_chunks": len(consultant.chunks),
        "taco_foods_loaded": len(consultant.taco_tool.foods) if consultant.taco_tool else 0,
        "knowledge_graph_stats": graph_stats,
        "ollama_available": consultant.llm_client.is_ollama_available(),
        "primary_local_model": consultant.llm_client.primary_model,
    }


@app.post("/consult", response_model=ConsultantResponse)
def consult_endpoint(request: ConsultRequest) -> ConsultantResponse:
    consultant = get_consultant()
    return consultant.consult(request.query, top_k=request.top_k)


def cli_main() -> None:
    query = (
        " ".join(sys.argv[1:])
        if len(sys.argv) > 1
        else "Como a fibra solúvel da aveia age para reduzir o colesterol LDL e a glicemia?"
    )
    consultant = get_consultant()
    res = consultant.consult(query)
    print("=" * 76)
    print(f"PERGUNTA ORIGINAL : {res.original_query}")
    if res.guardrail_triggered:
        print(f"GUARDRAIL ATIVADO : {res.intent_category}")
        print(f"QUERY REENQUADRADA: {res.effective_query}")
        print(f"AVISO LEGAL       : {res.legal_compliance_notice}")
    print("-" * 76)
    print(f"MODELO UTILIZADO  : {res.model_used} | GRAU DE EVIDÊNCIA: {res.evidence_grade}")
    print(f"\n[1] SÍNTESE DA EVIDÊNCIA:\n{res.evidence_summary}")
    print(f"\n[2] MECANISMO FISIOLÓGICO:\n{res.physiological_mechanism}")
    if res.graph_paths:
        print("\n[2.1] GRAFO DE CONHECIMENTO DE 4 CAMADAS (Alimento ➔ Composto ➔ Mecanismo ➔ Desfecho GRADE):")
        for gp in res.graph_paths:
            flag = "⚠️ CONTRAINDICADO" if gp.is_contraindicated_for_query else f"✅ {gp.evidence_grade}"
            print(
                f"  • [{flag}] {gp.food_node} ➔ {gp.compound_node} ➔ "
                f"{gp.mechanism_node} ➔ [{gp.effect_direction}] {gp.outcome_node}"
            )
    print(f"\n[3] ACHADOS DOS PROTOCOLOS CLÍNICOS:\n{res.protocol_findings}")
    if res.taco_records:
        print("\n[3.1] COMPOSIÇÃO DETERMINÍSTICA (TABELA TACO 4ª ED. / TBCA — POR 100g):")
        for rec in res.taco_records:
            nutr_str = ", ".join(f"{k}: {v}" for k, v in rec.nutrients_per_100g.items())
            print(
                f"  • {rec.description} ({rec.category}): {rec.energy_kcal} kcal, "
                f"Proteína: {rec.protein_g}g, Fibra: {rec.fiber_g}g | {nutr_str}"
            )
    print(f"\n[4] ALIMENTOS / COMPOSTOS RELACIONADOS:\n  • " + "\n  • ".join(res.food_sources_or_compounds))
    print("\n[5] CITAÇÕES RECUPERADAS (RAG HÍBRIDO):")
    for cite in res.citations:
        print(f"  - {cite}")
    print("=" * 76)


if __name__ == "__main__":
    cli_main()
