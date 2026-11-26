"""Guardrail legal da Lei 8.234/1991 (RN01 e RN02) para o Agente de Nutrição.

Entrada em cascata (issue #39), como o portão de risco (#48):

1. regras: as listas literais de antes e duas regras de dois sinais, mais gerais:
   - pedido de quantidade ou dose ("quantos gramas", "dose", "calcule", "g/kg") com primeira pessoa
     ou pedido ("eu", "meu", "devo", "posso", "preciso");
   - pedido de liberação de um alimento ("posso comer", "tudo bem eu comer") com condição de saúde
     (na mensagem ou num Fato do Usuário entregue ao agente) ou dado pessoal (peso, idade);
2. camada LLM local (`classificador_llm`, opcional): consultada só quando as regras não acionam;
   qualquer falha faz valer só as regras. Sem Ollama (CI, benchmark), só as regras.

Saída: com a pergunta restrita, as frases com número e unidade (mg, g/kg, kcal) saem da resposta
(`sem_quantidades`), e o aviso legal entra por código, nunca gerado pelo modelo.
"""

import json
import re
from typing import Any, Callable, Dict, List, Optional, Tuple

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

# Regras de dois sinais (issue #39).
_QUANTIDADE = re.compile(
    r"\b(quant[oa]s?|qual a quantidade|qual a dose|que dose)\b.{0,40}\b(gramas?|g|mg|mcg|ml|calorias?|kcal|"
    r"proteinas?|carboidratos?|gorduras?|fibras?|vitamina \w+|ferro|calcio|magnesio|zinco|omega\W?3|suplementos?|"
    r"whey|creatina|capsulas?|comprimidos?|colheres?|porcoes?|litros?|agua)\b"
    r"|\b(dose|dosagem|posologia)\b|\bcalcul\w*\b.{0,30}\b(necessidade|calorias?|kcal|proteina|dieta|macros?)\b"
    r"|\b\d+([.,]\d+)?\s*(g/kg|mg/kg|kcal)\b")
_PEDIDO_PESSOAL = re.compile(
    r"\b(eu|meu|minha|meus|minhas|me|mim|comigo|sou|tenho|estou|devo|deveria|posso|poderia|preciso|"
    r"pro meu|para mim|pra mim)\b|\b\d+\s*(kg|quilos|anos|cm)\b")
_LIBERACAO = re.compile(
    r"\b(posso|poderia|pode|tudo bem|tranquilo|e seguro|faz mal|e ruim|e perigoso|sem problema)\b.{0,40}"
    r"\b(comer|beber|tomar|consumir|ingerir|usar)\b"
    r"|\b(comer|beber|tomar|consumir|ingerir)\b.{0,60}\b(tudo bem|pode|posso|faz mal|certo|sem problema)\b")
_CONDICAO = re.compile(
    r"\b(diabet\w*|pre.?diabet\w*|glicemia alta|hipertens\w*|pressao alta|doenca renal|insuficiencia renal|"
    r"rins?|celiac\w*|gestante|gravida|gravidez|amamenta\w*|colesterol alto|triglicerides? alto|gastrite|"
    r"refluxo|cancer|tireoide|hipotireoid\w*|hipertireoid\w*|anemia|obesidade|bariatrica|gota|"
    r"alergia|intolerancia|doenca|sindrome|cardiaco|cardiopat\w*)\b")
_DADO_PESSOAL = re.compile(r"\b\d+\s*(kg|quilos|anos|cm)\b|\bmeus exames\b|\bmeu peso\b")

SISTEMA_PRESCRICAO = """Você classifica mensagens enviadas a um assistente educativo de nutrição, que NÃO pode fazer
prescrição individual (Lei 8.234/1991): calcular quantidades, doses ou calorias para a pessoa, montar dieta
ou cardápio para ela, ou liberar/proibir um alimento para alguém com uma condição de saúde.

"pedido_individual": true quando a mensagem pede uma quantidade, dose, meta ou plano para a própria pessoa,
ou pede liberação de um alimento para ela tendo uma condição de saúde ou dado pessoal.
"pedido_individual": false para perguntas gerais (o que as diretrizes recomendam, o que um alimento contém,
se algo faz bem em geral), mesmo em primeira pessoa quando não pedem quantidade nem liberação individual.
"Posso comer X?" ou "tudo bem comer X?" SEM condição de saúde nem dado pessoal na mensagem é dúvida geral:
false. Só vira pedido individual quando a pessoa cita uma condição de saúde (diabetes, pressão alta,
gravidez, doença renal...) ou dados dela (peso, idade, exames).

Exemplos:
- "Posso comer ovo todo dia?" -> false
- "Quero comer um chocolate amargo, tudo bem?" -> false
- "Sou diabético, posso comer chocolate?" -> true
- "Me passa o tanto certo de proteína pro meu caso" -> true
- "Quanto de proteína tem um ovo?" -> false

Responda só com JSON: {"pedido_individual": true ou false}"""

UNIDADE_DE_QUANTIDADE = re.compile(
    r"\d+([.,]\d+)?\s*(mg|mcg|µg|ug|g|kg|kcal|cal|ml|l|ui)\b(\s*/\s*(dia|kg|d|refeicao|refeição))?", re.IGNORECASE)


def sem_quantidades(texto: str) -> str:
    """Tira as frases com número e unidade (mg, g/kg, kcal...): com a pergunta pessoal, a mesma frase
    populacional funcionaria como prescrição (issue #39)."""
    from src.rag.verificador.citacoes import dividir_frases

    paragrafos = []
    for paragrafo in texto.split("\n\n"):
        frases = [f for f in dividir_frases(paragrafo) if not UNIDADE_DE_QUANTIDADE.search(f)]
        if frases:
            paragrafos.append(" ".join(frases))
    return "\n\n".join(paragrafos)


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

    # Camada LLM opcional (issue #39): chamável (sistema, usuário) -> JSON, como o ClienteJsonOllama.
    classificador_llm: Optional[Callable[[str, str], Optional[Dict[str, Any]]]] = None

    def _pelo_llm(self, user_query: str) -> bool:
        if self.classificador_llm is None:
            return False
        try:
            bruto = self.classificador_llm(SISTEMA_PRESCRICAO, json.dumps({"mensagem": user_query}, ensure_ascii=False))
        except Exception:  # LLM fora ou tempo esgotado: valem só as regras
            return False
        return isinstance(bruto, dict) and bruto.get("pedido_individual") is True

    def assess_and_reframe(self, user_query: str, condicao_de_saude: bool = False) -> GuardrailAssessment:
        """`condicao_de_saude`: um Fato do Usuário com condição de saúde foi entregue ao agente (#112)."""
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

        # Regras de dois sinais (issue #39).
        if _QUANTIDADE.search(norm) and _PEDIDO_PESSOAL.search(norm) and not (is_posology or is_diagnosis):
            is_diet = True
            triggered_rules.append("pedido de quantidade ou dose para a própria pessoa")
        if _LIBERACAO.search(norm) and (condicao_de_saude or _CONDICAO.search(norm) or _DADO_PESSOAL.search(norm)):
            is_diet = True
            triggered_rules.append("liberação de alimento para pessoa com condição de saúde ou dado pessoal")
        if not (is_diagnosis or is_posology or is_diet) and self._pelo_llm(user_query):
            is_diet = True
            triggered_rules.append("pedido individual (camada LLM)")

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
