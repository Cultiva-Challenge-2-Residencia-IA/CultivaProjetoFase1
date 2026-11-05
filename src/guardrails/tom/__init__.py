"""Guardrail de Tom: Sanitização de linguagem imperativa/prescritiva na saída do LLM."""

from src.agent.guardrails import FORBIDDEN_OUTPUT_IMPERATIVES, LegalGuardrail


def sanitize_prescriptive_tone(text: str) -> str:
    """Remove verbos prescritivos diretos ('você deve comer', 'prescrevo') garantindo tom informativo populacional."""
    return LegalGuardrail().sanitize_output_text(text)


__all__ = ["sanitize_prescriptive_tone", "FORBIDDEN_OUTPUT_IMPERATIVES"]
