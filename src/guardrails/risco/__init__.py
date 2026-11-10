"""Guardrails de risco.

- Sinais de risco à pessoa (RF-IA03): `detectar_risco` e a mensagem fixa `MENSAGEM_ACOLHIMENTO`.
- Risco clínico de contraindicação cruzada (ex.: doença renal crônica + potássio): `detect_clinical_risk_flags`.
"""


from typing import Set
from src.guardrails.risco.acolhimento import MENSAGEM_ACOLHIMENTO
from src.guardrails.risco.detector import AvaliacaoRisco, detectar_risco
from src.retrieval.hybrid_retriever import normalize_text

__all__ = ["AvaliacaoRisco", "MENSAGEM_ACOLHIMENTO", "detect_clinical_risk_flags", "detectar_risco"]

RENAL_POTASSIUM_TRIGGERS = [
    "doenca renal",
    "renal cronica",
    "problema nos rins",
    "problemas renais",
    "insuficiencia renal",
    "drc",
    "hipercalemia",
    "restricao de potassio",
    "cuidar do potassio",
    "sem ter potassio",
    "sem aumentar o potassio",
]


def detect_clinical_risk_flags(query: str) -> Set[str]:
    """Detecta condições clínicas de risco que exigem filtragem de contraindicações."""
    norm_q = normalize_text(query)
    flags: Set[str] = set()
    if any(kw in norm_q for kw in RENAL_POTASSIUM_TRIGGERS):
        flags.add("renal_potassium_restriction")
    if "anticoagulante" in norm_q or "varfarina" in norm_q or "calculo biliar" in norm_q:
        flags.add("biliary_or_anticoagulant_caution")
    return flags
