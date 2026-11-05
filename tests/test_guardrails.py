from src.agent.guardrails import LegalGuardrail


def test_safe_general_evidence_query_passes_without_restriction() -> None:
    guardrail = LegalGuardrail()
    query = "Como a beta-glucana da aveia ajuda a reduzir o colesterol LDL?"
    assessment = guardrail.assess_and_reframe(query)

    assert assessment.is_restricted_by_law_8234 is False
    assert assessment.intent_category == "SAFE_EVIDENCE_QUERY"
    assert assessment.reframed_population_query == query
    assert assessment.legal_notice_required is None


def test_diet_prescription_request_triggers_guardrail_and_reframes() -> None:
    guardrail = LegalGuardrail()
    query = (
        "Tenho 82kg e pré-diabetes. Monte um cardápio completo de 1800 kcal "
        "com café da manhã, almoço e jantar para mim."
    )
    assessment = guardrail.assess_and_reframe(query)

    assert assessment.is_restricted_by_law_8234 is True
    assert assessment.intent_category == "RESTRICTED_DIET_PRESCRIPTION"
    assert assessment.legal_notice_required is not None
    assert "8.234/1991" in assessment.legal_notice_required
    assert "in natura" in assessment.reframed_population_query.lower()


def test_clinical_diagnosis_request_triggers_guardrail() -> None:
    guardrail = LegalGuardrail()
    query = "Meus exames deram ferritina em 10 e LDL em 170. Faça meu diagnóstico nutricional."
    assessment = guardrail.assess_and_reframe(query)

    assert assessment.is_restricted_by_law_8234 is True
    assert assessment.intent_category == "RESTRICTED_CLINICAL_DIAGNOSIS"
    assert "feijões" in assessment.reframed_population_query.lower() or "carnes" in assessment.reframed_population_query.lower()


def test_supplement_posology_request_triggers_guardrail() -> None:
    guardrail = LegalGuardrail()
    query = "Quero ganhar massa muscular: me prescreva a dose personalizada de creatina e whey para meu peso de 70kg."
    assessment = guardrail.assess_and_reframe(query)

    assert assessment.is_restricted_by_law_8234 is True
    assert assessment.intent_category == "RESTRICTED_SUPPLEMENT_POSOLOGY"
    assert "suplementos" in assessment.reframed_population_query.lower() or "in natura" in assessment.reframed_population_query.lower()


def test_output_guardrail_sanitizes_imperative_prescriptions() -> None:
    guardrail = LegalGuardrail()
    unsafe_output = "Para melhorar seus exames, você deve comer 40g de aveia e tome 5g de creatina."
    sanitized = guardrail.sanitize_output_text(unsafe_output)

    assert "você deve comer" not in sanitized.lower()
    assert "tome 5" not in sanitized.lower()
    assert "protocolos clínicos" in sanitized.lower() or "ensaios clínicos" in sanitized.lower()
