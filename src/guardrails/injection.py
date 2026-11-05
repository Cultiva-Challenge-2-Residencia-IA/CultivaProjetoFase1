from __future__ import annotations


class PromptInjectionGuard:
    """Block direct prompt-injection attempts against the agent."""

    _patterns = (
        "ignore previous instructions",
        "ignore all instructions",
        "ignore as instruções anteriores",
        "ignore todas as instruções anteriores",
        "ignore todas as instruções",
        "override the system",
        "system prompt",
        "reveal the prompt",
        "revele as instruções internas",
        "remova as regras",
        "jailbreak",
        "instruções internas do sistema",
    )

    def should_block(self, text: str) -> bool:
        normalized = (text or "").lower()
        return any(pattern in normalized for pattern in self._patterns)

    def reason(self, text: str) -> str:
        return "prompt injection" if self.should_block(text) else "ok"
