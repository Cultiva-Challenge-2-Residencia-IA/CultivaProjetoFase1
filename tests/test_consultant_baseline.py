from src.agent.consultant_baseline import NutritionConsultantBaseline
from src.evaluation.run_benchmark import evaluate_baseline


def test_consultant_baseline_end_to_end_safe_query_on_guia_alimentar() -> None:
    consultant = NutritionConsultantBaseline(enable_ollama=False)
    response = consultant.consult(
        "Como utilizar óleos, gorduras, sal e açúcar nas preparações culinárias segundo o Guia Alimentar?"
    )

    assert response.guardrail_triggered is False
    assert response.legal_compliance_notice is None
    assert response.evidence_grade == "GUIDELINE_CONSENSUS"
    assert len(response.citations) > 0
    combined = (
        f"{response.evidence_summary} {response.physiological_mechanism} {response.protocol_findings}"
    ).lower()
    assert "pequenas quantidades" in combined or "preparações culinárias" in combined
    assert "sal" in combined or "açúcar" in combined


def test_consultant_baseline_end_to_end_restricted_query() -> None:
    consultant = NutritionConsultantBaseline(enable_ollama=False)
    response = consultant.consult(
        "Tenho 80kg e pré-diabetes. Monte um cardápio completo de 1800 kcal para mim."
    )

    assert response.guardrail_triggered is True
    assert response.intent_category == "RESTRICTED_DIET_PRESCRIPTION"
    assert response.legal_compliance_notice is not None
    assert "8.234/1991" in response.legal_compliance_notice
    assert len(response.retrieved_chunks) > 0


def test_benchmark_evaluation_achieves_high_recall_and_perfect_legal_compliance(tmp_path) -> None:
    report_file = tmp_path / "test_report.json"
    report = evaluate_baseline(report_path=report_file, enable_ollama=False)

    metrics = report["overall_metrics"]
    assert metrics["legal_guardrail_accuracy"] == 1.0
    assert metrics["mean_doc_recall_at_k"] >= 0.80
    assert report_file.exists()


def test_groq_api_client_synthesis(monkeypatch) -> None:
    consultant = NutritionConsultantBaseline(enable_ollama=True)
    consultant.llm_client.provider = "groq"
    consultant.llm_client.groq_api_key = "gsk_test_fake_key"
    consultant.llm_client.enable_groq = True

    def fake_call_groq(model_name: str, user_prompt: str):
        assert model_name == "openai/gpt-oss-120b"
        return {
            "evidence_summary": "A beta-glucana da aveia reduz o colesterol LDL-c segundo meta-análises.",
            "physiological_mechanism": "Aumento da viscosidade luminal intestinal e sequestro de ácidos biliares.",
            "protocol_findings": "Ingestão populacional estudada de 3 g/dia de beta-glucana.",
            "food_sources_or_compounds": ["Aveia (beta-glucana)"],
            "evidence_grade": "GRADE_A",
        }

    monkeypatch.setattr(consultant.llm_client, "_call_groq_model", fake_call_groq)
    res = consultant.consult("Como a fibra solúvel da aveia reduz o colesterol LDL?")
    assert res.model_used == "groq:openai/gpt-oss-120b"
    assert "beta-glucana" in res.evidence_summary.lower()
