import httpx


class ModeloOllama:
    """Modelo local servido pelo Ollama. Temperatura zero para reduzir variação.

    Nome do modelo e URL são obrigatórios e vêm da configuração (.env).
    """

    def __init__(self, modelo: str, url: str, timeout: float = 120.0):
        self.nome = modelo
        self._url = url.rstrip("/")
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
