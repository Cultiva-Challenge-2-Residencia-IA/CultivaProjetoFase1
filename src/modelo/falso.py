import re

_ID_TRECHO = re.compile(r"^\[([a-z0-9][a-z0-9-]*)\]", re.MULTILINE)


class ModeloFalso:
    """Modelo determinístico para testes e CI.

    Sem respostas programadas, cita o primeiro Trecho recebido na mensagem; se não houver
    Trecho, responde NAO_SEI. Com `respostas`, devolve cada uma em ordem (útil para testar
    guardrails de saída e a nova tentativa de citação).
    """

    nome = "falso"

    def __init__(self, respostas: list[str] | None = None):
        self._respostas = list(respostas or [])
        self.chamadas: list[tuple[str, str]] = []

    def gerar(self, sistema: str, mensagem: str) -> str:
        self.chamadas.append((sistema, mensagem))
        if self._respostas:
            return self._respostas.pop(0)
        ids = _ID_TRECHO.findall(mensagem)
        if not ids:
            return "NAO_SEI"
        return f"De acordo com o Guia Alimentar, vale priorizar o que o trecho indica [{ids[0]}]."
