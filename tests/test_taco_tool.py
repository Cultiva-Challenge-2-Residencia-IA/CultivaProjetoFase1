from src.agent.consultant_baseline import NutritionConsultantBaseline
from src.retrieval.taco_tool import TacoDeterministicTool


def test_taco_tool_loads_all_597_official_foods() -> None:
    tool = TacoDeterministicTool()
    assert len(tool.foods) >= 597


def test_taco_tool_resolves_castanha_do_para_and_exact_minerals() -> None:
    tool = TacoDeterministicTool()
    records, context_str = tool.auto_query_from_question(
        "Qual a quantidade exata em miligramas de magnésio, potássio e selênio em 100g de castanha-do-pará, semente de abóbora e feijão preto na tabela TACO?"
    )

    assert len(records) >= 3
    descriptions = [r.description for r in records]
    assert "Castanha-do-Brasil, crua" in descriptions
    assert "Semente de abóbora, crua (TBCA/TACO)" in descriptions
    assert any("Feijão, preto" in d for d in descriptions)

    castanha = next(r for r in records if r.description == "Castanha-do-Brasil, crua")
    assert castanha.nutrients_per_100g["Magnésio (mg)"] == 365.12
    assert castanha.nutrients_per_100g["Selênio (mcg)"] == 1917.0
    assert "365.12" in context_str
    assert "1917.0" in context_str


def test_taco_tool_ranks_foods_by_nutrient() -> None:
    tool = TacoDeterministicTool()
    top_fiber = tool.rank_foods_by_nutrient("fiber_g", "Fibra Alimentar (g)", limit=5)

    assert len(top_fiber) == 5
    vals = [r.nutrients_per_100g["Fibra Alimentar (g)"] for r in top_fiber]
    assert vals == sorted(vals, reverse=True)
    assert vals[0] >= 25.0


def test_consultant_integrates_taco_records_on_quantitative_query() -> None:
    consultant = NutritionConsultantBaseline(enable_ollama=False, enable_taco_tool=True)
    res = consultant.consult(
        "Quais alimentos do grupo das castanhas, nozes e feijões são destacados no Guia Alimentar e qual a quantidade exata em miligramas de magnésio e selênio em 100g na tabela TACO?"
    )

    assert res.retrieval_mode in {"HYBRID_RAG_PLUS_TACO_TOOL", "HYBRID_RAG_PLUS_GRAPH_AND_TACO"}
    assert len(res.taco_records) >= 2
    assert "365.12" in res.protocol_findings
    assert any("TACO_4ED_UNICAMP" in c for c in res.citations)
