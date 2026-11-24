"""Chamada ao LLM local que devolve JSON livre (issue #99): reescrita de consulta e Sincronizador.

Usa o Ollama local do ADR 0004, com `think` desligado e saída em JSON. Qualquer falha (Ollama fora,
tempo esgotado, JSON inválido) devolve None, e quem chamou segue o caminho sem LLM. O texto já chega
mascarado de quem chama (RNF05).
"""

import json
from typing import Any, Dict, Optional

import httpx

from src.config import OLLAMA_BASE_URL, OLLAMA_MODEL, OLLAMA_NUM_CTX, OLLAMA_THINK
from src.observabilidade import observacao


class ClienteJsonOllama:
    def __init__(self, nome: str, base_url: str = OLLAMA_BASE_URL, modelo: str = OLLAMA_MODEL,
                 timeout: float = 30.0, num_predict: int = 1024) -> None:
        self.nome, self.base_url, self.modelo = nome, base_url.rstrip("/"), modelo
        self.timeout, self.num_predict = timeout, num_predict

    def disponivel(self) -> bool:
        try:
            with httpx.Client(timeout=2.0) as cliente:
                return cliente.get(f"{self.base_url}/api/tags").status_code == 200
        except Exception:
            return False

    def __call__(self, sistema: str, usuario: str) -> Optional[Dict[str, Any]]:
        payload = {
            "model": self.modelo,
            "messages": [{"role": "system", "content": sistema}, {"role": "user", "content": usuario}],
            "format": "json", "stream": False, "think": OLLAMA_THINK,
            "options": {"temperature": 0.1, "num_ctx": OLLAMA_NUM_CTX, "num_predict": self.num_predict},
        }
        with observacao(self.nome, tipo="generation", model=self.modelo, input=payload["messages"]) as obs:
            try:
                with httpx.Client(timeout=self.timeout) as cliente:
                    resposta = cliente.post(f"{self.base_url}/api/chat", json=payload)
                    resposta.raise_for_status()
                    dados = resposta.json()
                conteudo = dados.get("message", {}).get("content", "")
                obs.update(output=conteudo, usage_details={
                    "input": int(dados.get("prompt_eval_count") or 0), "output": int(dados.get("eval_count") or 0)})
                bruto = json.loads(conteudo)
                return bruto if isinstance(bruto, dict) else None
            except Exception as exc:
                obs.update(level="ERROR", status_message=f"{type(exc).__name__}: {exc}")
                return None
