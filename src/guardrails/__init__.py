"""Pacote unificado de Guardrails (Prescrição Lei 8.234/91, Risco Clínico, Tom e Prompt Injection)."""

from src.guardrails.injection import has_prompt_injection
from src.guardrails.prescricao import LEGAL_COMPLIANCE_NOTICE, LegalGuardrail
from src.guardrails.risco import detect_clinical_risk_flags
from src.guardrails.tom import sanitize_prescriptive_tone

__all__ = [
    "LegalGuardrail",
    "LEGAL_COMPLIANCE_NOTICE",
    "detect_clinical_risk_flags",
    "sanitize_prescriptive_tone",
    "has_prompt_injection",
]
