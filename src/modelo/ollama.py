import os

import httpx


class ModeloOllama:
    """Modelo local servido pelo Ollama. Temperatura zero para reduzir variação."""

    def __init__(
        self,
        modelo: str | None = None,
        url: str | None = None,
        timeout: float = 120.0,
    ):
        self.nome = modelo or os.environ.get("CULTIVA_MODELO", "qwen2.5")
        self._url = (url or os.environ.get("CULTIVA_OLLAMA_URL", "http://localhost:11434")).rstrip(
            "/"
        )
        self._timeout = timeout

    @property
    def url(self) -> str:
        return self._url

    def modelos_disponiveis(self) -> list[str]:
        """Modelos baixados no Ollama. Levanta httpx.HTTPError se o servidor não responder."""
        resposta = httpx.get(f"{self._url}/api/tags", timeout=5.0)
        resposta.raise_for_status()
        return [m["name"] for m in resposta.json().get("models", [])]

    def gerar(self, sistema: str, mensagem: str) -> str:
        resposta = httpx.post(
            f"{self._url}/api/chat",
            json={
                "model": self.nome,
                "messages": [
                    {"role": "system", "content": sistema},
                    {"role": "user", "content": mensagem},
                ],
                "stream": False,
                "options": {"temperature": 0},
            },
            timeout=self._timeout,
        )
        resposta.raise_for_status()
        return resposta.json()["message"]["content"]
