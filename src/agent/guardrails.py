import re
from typing import List, Tuple

from src.models.schemas import GuardrailAssessment
from src.retrieval.hybrid_retriever import normalize_text

LAW_8234_COMPLIANCE_NOTICE = (
    "Nota de Conformidade Legal (Lei Federal nº 8.234/1991, Art. 3º - CFN): "
    "A prescrição dietética individualizada (cardápios com quantidades, calorias e horários personalizados), "
    "o diagnóstico nutricional clínico e a prescrição posológica individual de suplementos são atividades "
    "privativas do nutricionista habilitado. Abaixo estão apresentadas exclusivamente as evidências científicas "
    "populacionais, os mecanismos fisiológicos e o que indicam as diretrizes oficiais sobre o tema."
)

DIET_PRESCRIPTION_PATTERNS: List[Tuple[str, str]] = [
    (r"\bmonte\b.*\b(cardapio|dieta|plano alimentar)\b", "solicitação de montagem de cardápio/dieta"),
    (r"\bprescrev[ae]\b.*\b(dieta|cardapio|alimentacao)\b", "solicitação de prescrição dietética"),
    (r"\b\d{3,4}\s*kcal\b", "especificação de meta calórica individualizada"),
    (r"\bgramas exatas\b|\bquantas gramas devo comer\b", "cálculo de gramatura individualizada"),
    (r"\bcafe da manha,\s*almoco e jantar\b", "estruturação de cardápio diário por refeição"),
]

DIAGNOSIS_PATTERNS: List[Tuple[str, str]] = [
    (r"\bfaca meu diagnostico\b|\bdiagnostico nutricional\b", "solicitação de diagnóstico nutricional clínico"),
    (r"\bmeus exames deram\b.*\b(prescrev[ae]|diagnostico|o que devo tomar)\b", "interpretação diagnóstica/prescritiva de exames"),
]

SUPPLEMENT_POSOLOGY_PATTERNS: List[Tuple[str, str]] = [
    (r"\bprescrev[ae]\b.*\b(capsulas|miligramas|dose|suplemento|whey|creatina|ferro|omega)\b", "prescrição posológica de suplementos"),
    (r"\bquantas (capsulas|miligramas|gramas) de .* devo tomar\b", "posologia individualizada de suplemento"),
    (r"\bdose personalizada\b.*\bmeu peso\b", "cálculo de dose individual por peso corporal"),
]

RESTRICTIVE_QUERY_NOISE_PATTERNS = [
    r"monte um cardapio completo[^.]*",
    r"prescreva minha dieta[^.]*",
    r"faca meu diagnostico nutricional[^.]*",
    r"me prescreva quantas capsulas[^.]*",
    r"tenho \d+\s*kg[^,.]*",
    r"para meu peso de \d+\s*kg",
    r"\d{3,4}\s*kcal",
]

FORBIDDEN_OUTPUT_IMPERATIVES: List[Tuple[str, str]] = [
    (r"\bvoc[eê]\s+deve\s+comer\b", "os protocolos clínicos avaliam o consumo de"),
    (r"\bvoc[eê]\s+deve\s+tomar\b", "os estudos clínicos investigaram a administração de"),
    (r"\btome\s+(\d+)", r"nos ensaios clínicos foram utilizadas faixas de \1"),
    (r"\bcoma\s+(\d+)", r"nas diretrizes avaliam-se porções de referência de \1"),
    (r"\bseu\s+card[aá]pio\s+deve\s+conter\b", "as diretrizes alimentares destacam a presença de"),
    (r"\bprescrevo\s+para\s+voc[eê]\b", "a literatura científica descreve"),
]


class LegalGuardrail:
    """
    Implementa os Guardrails de Entrada (Intent Classification & Reframing) e
    de Saída (Bloqueio de linguagem prescritiva individual) conforme a Lei nº 8.234/91.
    """

    def assess_and_reframe(self, user_query: str) -> GuardrailAssessment:
        norm = normalize_text(user_query)
        triggered_rules: List[str] = []

        is_diagnosis = False
        is_posology = False
        is_diet = False

        for pattern, description in DIAGNOSIS_PATTERNS:
            if re.search(pattern, norm):
                is_diagnosis = True
                triggered_rules.append(description)

        for pattern, description in SUPPLEMENT_POSOLOGY_PATTERNS:
            if re.search(pattern, norm):
                is_posology = True
                triggered_rules.append(description)

        for pattern, description in DIET_PRESCRIPTION_PATTERNS:
            if re.search(pattern, norm):
                is_diet = True
                triggered_rules.append(description)

        if not (is_diagnosis or is_posology or is_diet):
            return GuardrailAssessment(
                intent_category="SAFE_EVIDENCE_QUERY",
                is_restricted_by_law_8234=False,
                triggered_rules=[],
                reframed_population_query=user_query.strip(),
                legal_notice_required=None,
            )

        if is_diagnosis:
            category = "RESTRICTED_CLINICAL_DIAGNOSIS"
        elif is_posology and not is_diet:
            category = "RESTRICTED_SUPPLEMENT_POSOLOGY"
        else:
            category = "RESTRICTED_DIET_PRESCRIPTION"

        reframed = self._reframe_to_population_evidence(user_query, norm)

        return GuardrailAssessment(
            intent_category=category,
            is_restricted_by_law_8234=True,
            triggered_rules=triggered_rules,
            reframed_population_query=reframed,
            legal_notice_required=LAW_8234_COMPLIANCE_NOTICE,
        )

    def _reframe_to_population_evidence(self, original_query: str, norm_query: str) -> str:
        """
        Extrai os tópicos clínicos/nutricionais da pergunta restrita e a reescreve como
        uma consulta PICO populacional voltada às diretrizes e mecanismos fisiológicos.
        """
        detected_themes: List[str] = []
        theme_keywords = [
            ("pre-diabetes", "pré-diabetes, controle glicêmico, fibras solúveis, carga glicêmica, HbA1c, alimentos in natura ou minimamente processados e redução de ultraprocessados"),
            ("diabetes", "diabetes tipo 2, controle glicêmico, fibras alimentares, HbA1c, alimentos in natura e restrição de ultraprocessados"),
            ("emagrecer", "prevenção do excesso de peso, densidade energética, alimentos in natura, comensalidade, atenção ao comer e evitar ultraprocessados"),
            ("perder peso", "balanço de calorias, alimentos in natura ou minimamente processados, hortaliças e evitar substitutos de refeição ultraprocessados"),
            ("colesterol", "dislipidemia, redução de colesterol LDL, fitoesteróis, gorduras insaturadas, alimentos in natura e exclusão de ultraprocessados"),
            ("ldl", "redução de colesterol LDL, receptores hepáticos, fitoesteróis, fibras solúveis e óleos vegetais"),
            ("ferritina", "biodisponibilidade do ferro heme e não-heme, vitamina C, ácido ascórbico, carnes, feijões e hortaliças"),
            ("ferro", "absorção de ferro dietético, facilitadores como ácido ascórbico, feijões, carnes e variedade alimentar nas refeições"),
            ("omega-3", "ácidos graxos ômega-3 marinhos EPA e DHA no metabolismo lipídico e PPAR-alfa"),
            ("massa muscular", "hipertrofia muscular, síntese proteica miofibrilar via mTORC1, leucina e fontes de proteínas em alimentos in natura como carnes, ovos e feijão com arroz"),
            ("hiperproteica", "aporte proteico populacional em treinamento resistido, leucina, mTORC1 e grupos de alimentos ricos em proteínas no almoço e jantar"),
            ("whey", "evidências clínicas sobre Whey Protein comparado a fontes alimentares proteicas in natura"),
            ("creatina", "mecanismo da creatina monohidratada na fosfocreatina/ATP, segurança renal e alimentação baseada em alimentos in natura"),
            ("hipertensao", "padrão alimentar DASH, equilíbrio sódio-potássio, uso em pequenas quantidades de sal e evitar ultraprocessados"),
            ("pressao", "manejo nutricional da pressão arterial, padrão DASH e redução do sal de cozinha"),
            ("cardapio", "exemplos de refeições brasileiras saudáveis no café da manhã, almoço e jantar com alimentos in natura"),
        ]

        for trigger, expansion in theme_keywords:
            if trigger in norm_query:
                detected_themes.append(expansion)

        if detected_themes:
            themes_str = "; ".join(detected_themes)
            return (
                f"Quais são as evidências científicas populacionais, mecanismos fisiológicos e protocolos "
                f"das diretrizes clínicas sobre: {themes_str}?"
            )

        cleaned = norm_query
        for pat in RESTRICTIVE_QUERY_NOISE_PATTERNS:
            cleaned = re.sub(pat, " ", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return (
            f"O que as diretrizes científicas e ensaios clínicos informam em nível populacional sobre: {cleaned}?"
        )

    def sanitize_output_text(self, text: str) -> str:
        """Garante que nenhum trecho da resposta contenha comandos prescritivos individuais."""
        sanitized = text
        for pattern, replacement in FORBIDDEN_OUTPUT_IMPERATIVES:
            sanitized = re.sub(pattern, replacement, sanitized, flags=re.IGNORECASE)
        return sanitized
