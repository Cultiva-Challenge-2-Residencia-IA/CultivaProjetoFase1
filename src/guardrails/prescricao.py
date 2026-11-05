from __future__ import annotations


class ScopeGate:
    """Reject requests outside the allowed nutritional scope."""

    _patterns = (
        "dieta",
        "emagrecer em",
        "meta calórica",
        "meta calorica",
        "prescrever",
        "receita fechada",
        "suplemento",
        "remédio",
        "medicamento",
        "diagnostico",
        "diagnóstico",
        "tratamento",
        "plano alimentar personalizado",
    )

    def should_block(self, text: str) -> bool:
        normalized = (text or "").lower()
        return any(pattern in normalized for pattern in self._patterns)

    def reason(self, text: str) -> str:
        return "escopo fora do permitido" if self.should_block(text) else "ok"
