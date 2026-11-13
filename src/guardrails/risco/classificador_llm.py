"""Camada semântica do detector de risco (issue #48): LLM local consultado quando o léxico não aciona.

Roda no Ollama local (ADR 0003): a mensagem analisada pode ser a de alguém em crise e não sai da
máquina. Qualquer falha (Ollama fora, modelo ausente, tempo limite, resposta inválida) devolve
`None`, e o fluxo segue só com o léxico, que é o piso.

Dois modos:
- `llama_guard`: modelos Llama Guard 3, que respondem "safe" ou "unsafe" seguido das categorias;
  conta como risco a S11 (suicídio e autolesão, inclusive transtorno alimentar).
- `politica`: modelo instruído com a política abaixo, escrita a partir das definições das três
  categorias do RF-IA03, sem frases de exemplo de nenhum conjunto de avaliação.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import re
import time
from typing import List, Optional

import httpx

CATEGORIAS = ("ideacao_suicida", "autolesao", "comportamento_alimentar_de_risco")

POLITICA = """Você é um classificador de segurança de um aplicativo educativo de nutrição para adultos.
Decida se a mensagem do usuário traz sinal de risco à própria pessoa, em uma destas categorias:

- ideacao_suicida: pensamentos, desejo, plano, preparação ou intenção de morrer ou de tirar a
  própria vida, inclusive dita de forma indireta, eufemística ou como despedida.
- autolesao: machucar o próprio corpo de propósito, por qualquer meio, inclusive para aliviar
  emoções ou como punição, ou esconder ferimentos feitos em si.
- comportamento_alimentar_de_risco: restrição alimentar extrema ou prolongada, ficar dias sem
  comer, metas de peso perigosamente baixas, vômito provocado, uso de laxantes, diuréticos ou
  remédios para emagrecer sem prescrição, exercício excessivo para compensar o que comeu, ou culpa
  e sofrimento intensos ligados a comer.

Não é risco: perguntas informativas sobre alimentação, dietas e suplementos; objetivos de peso
razoáveis; jejum ou exames com orientação médica; sintomas de doenças comuns; expressões
idiomáticas e exageros do dia a dia; assuntos que não falam da própria pessoa.

Na dúvida entre risco e não risco, prefira risco: deixar passar uma pessoa em crise é o erro grave.

Responda só com JSON, sem texto fora dele: {"risco": true ou false, "categoria": uma das três
categorias acima ou null}."""


@dataclass(frozen=True)
class ResultadoLLM:
    risco: bool
    categorias: List[str]
    segundos: float


class ClassificadorRiscoLLM:
    def __init__(self, modelo: str, base_url: str = "http://localhost:11434", timeout: float = 3.0,
                 modo: Optional[str] = None) -> None:
        self.modelo = modelo
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.modo = modo or ("llama_guard" if "llama-guard" in modelo else "politica")

    def _mensagens(self, texto: str) -> list:
        if self.modo == "llama_guard":
            return [{"role": "user", "content": texto}]
        return [{"role": "system", "content": POLITICA}, {"role": "user", "content": texto}]

    def _interpretar(self, conteudo: str) -> Optional[List[str]]:
        """Categorias de risco detectadas; lista vazia se não há risco; None se a saída é inválida."""
        conteudo = conteudo.strip()
        if self.modo == "llama_guard":
            linhas = [linha.strip().lower() for linha in conteudo.splitlines() if linha.strip()]
            if not linhas or linhas[0] not in ("safe", "unsafe"):
                return None
            if linhas[0] == "safe":
                return []
            codigos = re.findall(r"s\d+", " ".join(linhas[1:]))
            return ["autolesao_ou_suicidio"] if "s11" in codigos else []
        achado = re.search(r"\{.*\}", conteudo, re.S)
        if not achado:
            return None
        try:
            dados = json.loads(achado.group(0))
        except json.JSONDecodeError:
            return None
        if not isinstance(dados.get("risco"), bool):
            return None
        if not dados["risco"]:
            return []
        categoria = dados.get("categoria")
        return [categoria if categoria in CATEGORIAS else "risco_nao_categorizado"]

    def classificar(self, texto: str) -> Optional[ResultadoLLM]:
        payload = {
            "model": self.modelo,
            "messages": self._mensagens(texto),
            "stream": False,
            "options": {"temperature": 0, "num_predict": 40},
        }
        if self.modo == "politica":
            payload["format"] = "json"
        inicio = time.perf_counter()
        try:
            with httpx.Client(timeout=self.timeout) as cliente:
                resposta = cliente.post(f"{self.base_url}/api/chat", json=payload)
                resposta.raise_for_status()
                conteudo = resposta.json().get("message", {}).get("content", "")
        except Exception:
            return None
        categorias = self._interpretar(conteudo)
        if categorias is None:
            return None
        return ResultadoLLM(risco=bool(categorias), categorias=categorias,
                            segundos=time.perf_counter() - inicio)
