"""Os candidatos da issue #52, todos com o mesmo LLM do Ollama local.

Cada candidato responde a uma pergunta só: **a resposta é sustentada pelos Trechos?** O "não sei"
em Nutrição fora do corpus usa a mesma checagem: se a resposta gerada não é sustentada pelos
Trechos recuperados, ela vira "não sei". A exceção é o `direto_pre`, que decide antes de gerar,
perguntando se os Trechos respondem a pergunta.

- `direto_pre`: chamada direta ao Ollama, antes da geração (os Trechos respondem a pergunta?);
- `direto_pos`: chamada direta ao Ollama, depois da geração (a resposta é sustentada?);
- `nemo`: NeMo Guardrails, trilho de saída `self check facts`, com o prompt da documentação;
- `guardrails_ai`: Guardrails AI, validador `ProvenanceLLM` (frase a frase, com os `top_k` Trechos
  mais próximos por embeddings), chamando o mesmo Ollama pelo LiteLLM.

Os prompts dos frameworks são os da documentação de cada um, sem ajuste: o que se mede é o
framework como ele é distribuído. Os prompts da chamada direta foram escritos antes de medir.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

import httpx

from src.evaluation.comparacao_guardrails import config

PROMPT_PRE = """Você confere se um material de consulta permite responder uma pergunta de Nutrição.
Leia a PERGUNTA e os TRECHOS. Responda "responde": true só se os TRECHOS trazem a informação
necessária para responder a pergunta. Se eles falam de outro assunto, ou só tocam no tema sem
responder, use false. Não use conhecimento próprio.
Responda só com JSON: {"responde": true | false}"""

PROMPT_POS = """Você confere se uma RESPOSTA é sustentada pelos TRECHOS de um material de consulta.
A RESPOSTA é sustentada só se TODAS as afirmações dela estão nos TRECHOS, diretamente ou por
paráfrase fiel. Uma afirmação que acrescenta número, estudo, órgão, mecanismo ou conclusão que
não está nos TRECHOS torna a RESPOSTA não sustentada, mesmo que seja verdadeira.
Responda só com JSON: {"sustentada": true | false, "afirmacao_sem_base": "texto ou vazio"}"""

# Prompt da documentação do NeMo Guardrails para a tarefa self_check_facts (fact-checking.mdx).
PROMPT_NEMO = (
    "You are given a task to identify if the hypothesis is grounded and entailed to the evidence.\n"
    "You will only use the contents of the evidence and not rely on external knowledge.\n"
    'Answer with yes/no. "evidence": {{ evidence }} "hypothesis": {{ response }} "entails":'
)


@dataclass
class Veredito:
    sustentada: Optional[bool]
    segundos: float
    chamadas: int = 1
    detalhe: Dict[str, Any] = field(default_factory=dict)
    erro: Optional[str] = None


def _trechos_texto(trechos: List[str]) -> str:
    return "\n\n".join(f"[T{i}] {t}" for i, t in enumerate(trechos, 1)) or "(nenhum trecho)"


class _Ollama:
    def __init__(self, url: str = config.OLLAMA_URL, modelo: str = config.MODELO) -> None:
        self.url, self.modelo = url, modelo
        self.cliente = httpx.Client(timeout=config.TIMEOUT)

    def json(self, sistema: str, usuario: str) -> Dict[str, Any]:
        r = self.cliente.post(f"{self.url}/api/chat", json={
            "model": self.modelo, "stream": False, "format": "json", "think": False,
            "messages": [{"role": "system", "content": sistema}, {"role": "user", "content": usuario}],
            "options": {"temperature": config.TEMPERATURA, "seed": config.SEMENTE, "num_ctx": config.NUM_CTX},
        })
        r.raise_for_status()
        return json.loads(r.json()["message"]["content"])


class DiretoPre:
    nome = "direto_pre"
    antes_da_geracao = True

    def __init__(self, llm: Optional[_Ollama] = None) -> None:
        self.llm = llm or _Ollama()

    def verificar(self, pergunta: str, trechos: List[str], resposta: str = "") -> Veredito:
        inicio = time.perf_counter()
        try:
            dados = self.llm.json(PROMPT_PRE, f"PERGUNTA:\n{pergunta}\n\nTRECHOS:\n{_trechos_texto(trechos)}")
            return Veredito(bool(dados.get("responde")), time.perf_counter() - inicio, detalhe=dados)
        except Exception as e:  # noqa: BLE001 - o erro vira dado da medição
            return Veredito(None, time.perf_counter() - inicio, erro=f"{type(e).__name__}: {e}")


class DiretoPos:
    nome = "direto_pos"
    antes_da_geracao = False

    def __init__(self, llm: Optional[_Ollama] = None) -> None:
        self.llm = llm or _Ollama()

    def verificar(self, pergunta: str, trechos: List[str], resposta: str) -> Veredito:
        inicio = time.perf_counter()
        try:
            dados = self.llm.json(PROMPT_POS, f"TRECHOS:\n{_trechos_texto(trechos)}\n\nRESPOSTA:\n{resposta}")
            return Veredito(bool(dados.get("sustentada")), time.perf_counter() - inicio, detalhe=dados)
        except Exception as e:  # noqa: BLE001
            return Veredito(None, time.perf_counter() - inicio, erro=f"{type(e).__name__}: {e}")


class NeMo:
    """Trilho de saída `self check facts` do NeMo Guardrails, chamado por `LLMRails.check`."""

    nome = "nemo"
    antes_da_geracao = False

    def __init__(self, url: str = config.OLLAMA_URL, modelo: str = config.MODELO) -> None:
        from nemoguardrails import LLMRails, RailsConfig

        yaml = f"""
models:
  - type: main
    engine: ollama
    model: {modelo}
    parameters:
      base_url: {url}/v1
      temperature: {config.TEMPERATURA}
rails:
  output:
    flows:
      - self check facts
prompts:
  - task: self_check_facts
    content: |-
{chr(10).join('      ' + linha for linha in PROMPT_NEMO.splitlines())}
"""
        self.rails = LLMRails(RailsConfig.from_content(yaml_content=yaml))

    def verificar(self, pergunta: str, trechos: List[str], resposta: str) -> Veredito:
        inicio = time.perf_counter()
        try:
            resultado = self.rails.check([
                {"role": "context", "content": {"relevant_chunks": "\n\n".join(trechos), "check_facts": True}},
                {"role": "user", "content": pergunta},
                {"role": "assistant", "content": resposta},
            ])
            status = str(getattr(resultado, "status", ""))
            bloqueada = "block" in status.lower()
            return Veredito(not bloqueada, time.perf_counter() - inicio,
                            detalhe={"status": status, "rails": str(getattr(resultado, "rail", ""))})
        except Exception as e:  # noqa: BLE001
            return Veredito(None, time.perf_counter() - inicio, erro=f"{type(e).__name__}: {e}")


def _embed_fastembed() -> Callable[[Any], Any]:
    """Embeddings do próprio projeto (`paraphrase-multilingual-MiniLM-L12-v2`, local), normalizados."""
    import numpy as np
    from fastembed import TextEmbedding

    from src.config import EMBEDDING_MODEL_NAME

    modelo = TextEmbedding(model_name=EMBEDDING_MODEL_NAME)

    def embed(textos: Any) -> Any:
        lista = [textos] if isinstance(textos, str) else list(textos)
        vetores = np.array(list(modelo.embed(lista)), dtype=float)
        vetores /= np.linalg.norm(vetores, axis=1, keepdims=True)
        return vetores

    return embed


class GuardrailsAI:
    """Validador `ProvenanceLLM` do Guardrails AI, frase a frase."""

    nome = "guardrails_ai"
    antes_da_geracao = False

    def __init__(self, url: str = config.OLLAMA_URL, modelo: str = config.MODELO, top_k: int = 3) -> None:
        import os

        # O Guardrails AI envia telemetria (OpenTelemetry) a um servidor externo por padrão. Ela fica
        # desligada aqui (ADR 0003): pela variável padrão do OpenTelemetry e pela configuração do
        # próprio Guardrails, sem depender do ~/.guardrailsrc de quem roda.
        os.environ["OTEL_SDK_DISABLED"] = "true"
        os.environ.setdefault("OLLAMA_API_BASE", url)
        from guardrails import Guard
        from guardrails.classes.rc import RC
        from guardrails.utils.hub_telemetry_utils import HubTelemetry
        from guardrails.settings import settings
        from guardrails_ai.provenance_llm import ProvenanceLLM

        settings.rc = RC(enable_metrics=False)
        self.embed = _embed_fastembed()
        self.validador = ProvenanceLLM(validation_method="sentence", llm_callable=f"ollama_chat/{modelo}",
                                       top_k=top_k, on_fail="noop")
        self.guard = Guard()
        settings.rc.enable_metrics = False
        self.guard.configure(allow_metrics_collection=False)
        HubTelemetry()._enabled = False
        self.guard.use(self.validador)

    def verificar(self, pergunta: str, trechos: List[str], resposta: str) -> Veredito:
        inicio = time.perf_counter()
        try:
            resultado = self.guard.validate(resposta, metadata={"sources": trechos, "embed_function": self.embed,
                                                                "pass_on_invalid": False})
            frases = len([f for f in resposta.split(". ") if f.strip()])
            return Veredito(bool(resultado.validation_passed), time.perf_counter() - inicio, chamadas=max(frases, 1),
                            detalhe={"falhas": [str(getattr(s, "failure_reason", "") or "")[:300] for s in
                                                (resultado.validation_summaries or [])][:3]})
        except Exception as e:  # noqa: BLE001
            return Veredito(None, time.perf_counter() - inicio, erro=f"{type(e).__name__}: {e}")


FABRICAS = {"direto_pre": DiretoPre, "direto_pos": DiretoPos, "nemo": NeMo, "guardrails_ai": GuardrailsAI}


def criar(nome: str):
    return FABRICAS[nome]()
