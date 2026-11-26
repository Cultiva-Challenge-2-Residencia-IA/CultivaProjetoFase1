"""Guardrail de entrada e de saída do Agente de Saúde Física (issue #99).

Mesmo papel do guardrail da Lei 8.234/1991 em Nutrição (`src/agent/guardrails.py`):

- **Lei 9.696/1998:** prescrever e orientar o treino de uma pessoa é atribuição do profissional
  de Educação Física. Pedido de treino individual é marcado (Pedido individual): a busca usa a pergunta da pessoa e a
  síntese recebe a instrução de responder de forma geral (issue #118), com nota legal.
- **Sem diagnóstico:** pergunta sobre a dor ou a lesão da própria pessoa recebe evidência geral e
  a indicação de um profissional (médico ou fisioterapeuta), nunca um diagnóstico.

Sinais de alerta (dor no peito, desmaio, lesão aguda) não ficam aqui: são um Portão do
Orquestrador, que vale para todos os chats (`src/guardrails/alerta`).
"""

import re
from typing import List, Tuple

from src.models.schemas import GuardrailAssessment
from src.retrieval.hybrid_retriever import normalize_text

AVISO_LEI_9696 = (
    "Nota de Conformidade Legal (Lei Federal nº 9.696/1998 - CONFEF): a prescrição e a orientação "
    "de um programa de exercícios para uma pessoa são atribuições do profissional de Educação "
    "Física, e a avaliação de dor ou lesão cabe a um médico ou fisioterapeuta. Abaixo estão só o que "
    "as diretrizes e estudos indicam em nível populacional."
)

PRESCRICAO_DE_TREINO: List[Tuple[str, str]] = [
    (r"\b(monte|montar|crie|criar|faca|fazer|prescrev\w*|elabor\w*)\b.*\b(treino|plano de treino|programa de"
     r" exercicios?|ficha|rotina de exercicios?)\b.*\b(para mim|pra mim|meu|minha)\b",
     "montagem de treino individual"),
    (r"\b(monte|crie|prescreva|faca)\b.*\b(meu|minha) (treino|ficha|rotina)\b", "montagem de treino individual"),
    (r"\bquant[oa]s (series|repeticoes|vezes|minutos|quilos|kg)\b.*\b(eu devo|devo|eu tenho que|tenho que|eu"
     r" preciso)\b", "dosagem individual de treino"),
    (r"\b(eu devo|devo|eu preciso|preciso)\b.*\bquant[oa]s (series|repeticoes|vezes|minutos|quilos|kg)\b",
     "dosagem individual de treino"),
    (r"\bqual (peso|carga) (eu )?(devo|tenho que) (usar|levantar|pegar)\b", "carga individual de treino"),
]

DIAGNOSTICO_DE_LESAO: List[Tuple[str, str]] = [
    (r"\b(o que e|o que sera|o que pode ser|e normal|e grave)\b.*\b(essa|esta|minha|meu)\b.*\b(dor|lesao|inchaco"
     r"|estalo)\b", "diagnóstico de dor ou lesão individual"),
    (r"\b(essa|esta|minha)\b \b(dor|lesao)\b.*\b(e|sera|pode ser) (uma? )?(tendinite|lesao|ruptura|hernia|grave)\b",
     "diagnóstico de dor ou lesão individual"),
    (r"\b(tenho|estou com)\b.*\b(tendinite|hernia|lesao|ruptura)\b.*\b(o que (eu )?faco|como (eu )?trato|qual"
     r" tratamento)\b", "tratamento de lesão individual"),
]

RUIDO_INDIVIDUAL = [
    r"\b(monte|montar|crie|criar|faca|prescreva|elabore)\b",
    r"\b(para mim|pra mim|eu devo|devo|eu tenho que|tenho que|eu preciso|preciso)\b",
    r"\b(meu|minha|meus|minhas)\b",
    r"\btenho \d+\s*(kg|anos)\b[^,.]*",
    r"\b\d+\s*(kg|anos)\b",
]

IMPERATIVOS_PROIBIDOS: List[Tuple[str, str]] = [
    (r"\bvoc[eê]\s+deve\s+(fazer|treinar|correr|levantar|praticar|realizar)\b", "as diretrizes descrevem"),
    (r"\bfa[cç]a\s+(\d+)\s+s[eé]ries\b", r"os estudos avaliaram \1 séries"),
    (r"\bseu\s+treino\s+deve\b", "os programas estudados"),
    (r"\bprescrevo\b", "a literatura descreve"),
]


class GuardrailSaudeFisica:
    """Mesma interface do `LegalGuardrail` de Nutrição: avaliação de entrada e saneamento da saída."""

    def assess_and_reframe(self, user_query: str, condicao_de_saude: bool = False) -> GuardrailAssessment:
        """`condicao_de_saude` vem do Projetor de contexto; a Lei 9.696 não muda por ela (o guardrail
        de prescrição da issue #39 é o da Lei 8.234, no Agente de Nutrição)."""
        norm = normalize_text(user_query)
        prescricao = [d for p, d in PRESCRICAO_DE_TREINO if re.search(p, norm)]
        diagnostico = [d for p, d in DIAGNOSTICO_DE_LESAO if re.search(p, norm)]
        if not prescricao and not diagnostico:
            return GuardrailAssessment(
                intent_category="SAFE_EVIDENCE_QUERY",
                is_restricted_by_law_8234=False,
                triggered_rules=[],
                reframed_population_query=user_query.strip(),
                legal_notice_required=None,
            )
        categoria = "RESTRICTED_INJURY_DIAGNOSIS" if diagnostico else "RESTRICTED_EXERCISE_PRESCRIPTION"
        return GuardrailAssessment(
            intent_category=categoria,
            is_restricted_by_law_8234=True,
            triggered_rules=prescricao + diagnostico,
            reframed_population_query=self._pergunta_populacional(user_query),
            legal_notice_required=AVISO_LEI_9696,
        )

    @staticmethod
    def _pergunta_populacional(pergunta: str) -> str:
        tema = pergunta.strip().rstrip("?.!")
        for padrao in RUIDO_INDIVIDUAL:
            tema = re.sub(padrao, " ", tema, flags=re.I)
        tema = re.sub(r"\s+", " ", tema).strip(" ,;:")
        return (
            "O que as diretrizes de atividade física e os estudos recomendam, em nível populacional, "
            f"para adultos sobre: {tema}?"
        )

    def sanitize_output_text(self, text: str) -> str:
        """Tira da resposta comandos de treino dirigidos ao usuário."""
        for padrao, troca in IMPERATIVOS_PROIBIDOS:
            text = re.sub(padrao, troca, text, flags=re.IGNORECASE)
        return text
