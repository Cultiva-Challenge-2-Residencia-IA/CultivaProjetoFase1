"""Guardrail de Prompt Injection / Jailbreak tentando contornar a Lei Federal nº 8.234/1991."""

import re

PROMPT_INJECTION_PATTERNS = [
    r"\bignore\s+(?:todas\s+as\s+)?(?:instru[cç][oõ]es|regras)\s+anteriores\b",
    r"\bfinja\s+que\s+(?:voc[eê]\s+)?[eé]\s+um\s+nutricionista\b",
    r"\bmodo\s+desenvolvedor\b",
    r"\bdesative\s+o\s+guardrail\b",
    r"\besque[cç]a\s+a\s+lei\s+8\.?234\b",
]


def has_prompt_injection(query: str) -> bool:
    """Retorna True se a consulta tentar manipular o prompt do sistema para burlar limites ético-legais."""
    lowered = query.lower()
    return any(re.search(pat, lowered) for pat in PROMPT_INJECTION_PATTERNS)
