from __future__ import annotations


class RiskGate:
    """Deterministic guardrail for high-risk nutrition and mental health situations."""

    _patterns = (
        "me matar",
        "quero me matar",
        "suicidio",
        "suicídio",
        "ideação suicida",
        "não quero viver",
        "autolesão",
        "autolesao",
        "vou me cortar",
        "vou me machucar",
        "vomitando após cada refeição",
        "vomito após cada refeição",
        "pular refeições",
        "pular refeição",
        "não comer por dias",
        "compulsão alimentar extrema",
        "não consigo parar de comer",
    )

    def should_block(self, text: str) -> bool:
        normalized = (text or "").lower()
        return any(pattern in normalized for pattern in self._patterns)

    def reason(self, text: str) -> str:
        return "risco" if self.should_block(text) else "ok"
