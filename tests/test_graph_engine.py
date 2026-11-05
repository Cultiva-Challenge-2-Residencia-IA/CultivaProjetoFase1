from src.agent.consultant_baseline import NutritionConsultantBaseline
from src.retrieval.graph_engine import CausalKnowledgeGraphEngine


def test_4layer_graph_builds_valid_networkx_structure() -> None:
    engine = CausalKnowledgeGraphEngine()
    stats = engine.get_graph_stats()

    assert stats["total_causal_paths"] >= 14
    assert stats["FOOD"] >= 12
    assert stats["COMPOUND"] >= 12
    assert stats["MECHANISM"] >= 12
    assert stats["OUTCOME"] >= 8
    assert stats["total_edges"] == stats["total_causal_paths"] * 3


def test_graph_traversal_distinguishes_curcumin_alone_vs_piperine_synergy() -> None:
    engine = CausalKnowledgeGraphEngine()
    paths, context_str = engine.traverse_for_query(
        "A cúrcuma pura funciona ou precisa da piperina para inibir a glicuronidação e ser absorvida?"
    )

    path_ids = {p.path_id for p in paths}
    assert "PATH_CURCUMIN_PIPERINE_SYNERGY" in path_ids
    assert "PATH_CURCUMIN_ALONE_LOW_BIO" in path_ids
    assert "2000%" in context_str or "glicuronidação" in context_str


def test_graph_traversal_flags_renal_potassium_contraindication_and_boosts_safe_path() -> None:
    engine = CausalKnowledgeGraphEngine()
    paths, context_str = engine.traverse_for_query(
        "Qual estratégia reduz a pressão arterial e melhora o HOMA-IR sem elevar o potássio sérico na doença renal crônica?"
    )

    path_ids = [p.path_id for p in paths]
    assert "PATH_MUFA_FIBER_BP_HOMA_DRC_SAFE" in path_ids
    assert "PATH_DASH_POTASSIUM_BP" in path_ids

    dash_path = next(p for p in paths if p.path_id == "PATH_DASH_POTASSIUM_BP")
    safe_path = next(p for p in paths if p.path_id == "PATH_MUFA_FIBER_BP_HOMA_DRC_SAFE")

    assert dash_path.is_contraindicated_for_query is True
    assert safe_path.is_contraindicated_for_query is False
    assert "CONTRAINDICADO" in context_str


def test_consultant_integrates_both_graph_and_taco_tools() -> None:
    consultant = NutritionConsultantBaseline(
        enable_ollama=False,
        enable_taco_tool=True,
        enable_graph_engine=True,
    )
    res = consultant.consult(
        "Como o feijão com laranja melhora a absorção do ferro e quanto de ferro tem no feijão preto segundo a TACO?"
    )

    assert res.retrieval_mode == "HYBRID_RAG_PLUS_GRAPH_AND_TACO"
    assert len(res.graph_paths) >= 1
    assert len(res.taco_records) >= 1
    assert any("KG_4LAYER_PICO_GRADE" in c for c in res.citations)
    assert any("TACO_4ED_UNICAMP" in c for c in res.citations)
