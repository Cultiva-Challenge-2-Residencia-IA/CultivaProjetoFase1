"""Observabilidade opcional com Langfuse.

Proposta técnica, ainda não documentada na Documentacao-Cultiva; o que pode ir para o Langfuse e
para onde está no ADR 0003. Quando `LANGFUSE_ATIVO` é falso (padrão, inclusive no CI), o Langfuse
nem é importado e todas as funções daqui viram no-ops, então o benchmark e os testes não mudam.

Garantias com o Langfuse ligado:

- o destino é o `LANGFUSE_BASE_URL` da configuração, passado ao SDK de forma explícita (o padrão
  do SDK é a nuvem). Fora de `localhost`, só com `ALLOW_EXTERNAL_LANGFUSE=true`;
- todo `input`, `output` e `metadata` de toda observação passa por `mascarar_estrutura` (máscara
  do RNF05) dentro do próprio SDK, antes de ser gravado. Se a máscara falhar, o SDK grava um
  marcador no lugar do dado, e não o dado;
- o texto dos Fatos do Usuário (issue #112) não é registrado: todo fato carregado ou extraído no
  processo entra em `ocultar_fatos`, e a máscara troca o texto por "[fato do usuário: <categoria>]"
  nos prompts da reescrita, da extração e da síntese;
- mensagem que o portão de risco detecta não é registrada: o consultor grava só as categorias
  (veja `NutritionConsultantBaseline.consult`), inclusive quando quem detecta é a camada LLM local
  (#48). Sem essa camada, vale só o léxico, que deixa passar a maioria das frases de risco novas;
  essas são registradas como qualquer pergunta, só com a máscara.

A máscara é defesa adicional, não anonimização (ADR 0003). O pacote fica no grupo opcional
`observabilidade`: `uv sync --group observabilidade`.

Uso:

    with observacao("retrieve", tipo="retriever", input={"query": q}) as obs:
        ...
        obs.update(output=resumo)
"""

import subprocess
import sys
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

from src.config import (
    ALLOW_EXTERNAL_LANGFUSE,
    LANGFUSE_ATIVO,
    LANGFUSE_BASE_URL,
    LANGFUSE_PEDIDO,
    LANGFUSE_RELEASE,
    destino_local,
)
from src.guardrails.pii import mascarar_dados_pessoais

_cliente: Any = None
_propagar: Any = None
# Texto de Fato do Usuário -> categoria, para a máscara (issue #112). Só cresce com os fatos que o
# processo carregou ou extraiu; a lista é lida pela máscara do SDK, possivelmente em outra thread.
_fatos_ocultos: Dict[str, str] = {}
_trava_fatos = threading.Lock()


def ocultar_fatos(fatos: Any) -> None:
    """Registra (texto, categoria) de Fatos do Usuário para nunca irem em texto ao Langfuse."""
    with _trava_fatos:
        for texto, categoria in fatos:
            if texto and len(texto) >= 4:
                _fatos_ocultos[texto] = categoria


def _sem_fatos(texto: str) -> str:
    with _trava_fatos:
        conhecidos = sorted(_fatos_ocultos.items(), key=lambda item: -len(item[0]))
    for fato, categoria in conhecidos:
        if fato in texto:
            texto = texto.replace(fato, f"[fato do usuário: {categoria}]")
    return texto


def mascarar_estrutura(dado: Any) -> Any:
    """Aplica a máscara de dados pessoais (e dos Fatos do Usuário) a todo texto dentro de
    dicionários, listas e tuplas."""
    if isinstance(dado, str):
        return mascarar_dados_pessoais(_sem_fatos(dado))
    if isinstance(dado, dict):
        return {chave: mascarar_estrutura(valor) for chave, valor in dado.items()}
    if isinstance(dado, (list, tuple)):
        return [mascarar_estrutura(valor) for valor in dado]
    return dado


def _mascara_do_sdk(*, data: Any, **_: Any) -> Any:
    return mascarar_estrutura(data)


def versao_do_codigo() -> str:
    """`LANGFUSE_RELEASE` ou o commit atual do Git; "desconhecida" fora de um repositório."""
    if LANGFUSE_RELEASE:
        return LANGFUSE_RELEASE
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short=12", "HEAD"],
            cwd=Path(__file__).resolve().parent,
            capture_output=True,
            text=True,
            timeout=2,
            check=True,
        ).stdout.strip() or "desconhecida"
    except (OSError, subprocess.SubprocessError):
        return "desconhecida"


if LANGFUSE_ATIVO:
    try:
        from langfuse import Langfuse, propagate_attributes
    except ImportError as exc:  # pragma: no cover - depende do ambiente
        raise ImportError(
            "CULTIVA_LANGFUSE=true, mas o pacote langfuse não está instalado. "
            "Rode `uv sync --group observabilidade`."
        ) from exc

    # O construtor registra o cliente; base_url explícito impede o SDK de cair na nuvem.
    _cliente = Langfuse(base_url=LANGFUSE_BASE_URL, mask=_mascara_do_sdk, release=versao_do_codigo())
    _propagar = propagate_attributes
elif LANGFUSE_PEDIDO and not destino_local(LANGFUSE_BASE_URL) and not ALLOW_EXTERNAL_LANGFUSE:
    print(
        f"Langfuse desligado: {LANGFUSE_BASE_URL} não é local. Para enviar traces a outro servidor, "
        "defina ALLOW_EXTERNAL_LANGFUSE=true (veja o ADR 0003).",
        file=sys.stderr,
    )


class _ObservacaoNula:
    """Substituta da observação do Langfuse quando a observabilidade está desligada."""

    def update(self, **_: Any) -> "_ObservacaoNula":
        return self

    def score(self, **_: Any) -> None:
        return None

    def score_trace(self, **_: Any) -> None:
        return None


def ativo() -> bool:
    return _cliente is not None


def cliente() -> Any:
    """Cliente do Langfuse, ou None quando a observabilidade está desligada."""
    return _cliente


@contextmanager
def observacao(nome: str, tipo: str = "span", trace_id: Optional[str] = None, **kwargs: Any) -> Iterator[Any]:
    """Abre uma observação aninhada à atual (span, generation, retriever, tool, guardrail...).

    `trace_id` só vale para a observação raiz: fixa o id do trace (veja `id_do_trace`).
    """
    if _cliente is None:
        yield _ObservacaoNula()
        return
    if trace_id:
        kwargs["trace_context"] = {"trace_id": trace_id}
    with _cliente.start_as_current_observation(name=nome, as_type=tipo, **kwargs) as obs:
        yield obs


def id_do_trace(response_id: str) -> Optional[str]:
    """Id do trace derivado do `response_id`, para o feedback achar o trace da resposta (RF-IA15)."""
    if _cliente is None:
        return None
    return _cliente.create_trace_id(seed=response_id)


def registrar_feedback_incorreto(response_id: str, detalhe: Optional[str]) -> None:
    """Grava o feedback de resposta incorreta como score `resposta_incorreta` no trace da resposta.

    O comentário é texto livre do usuário e vai mascarado (RNF05). No-op com o Langfuse desligado.
    """
    if _cliente is None:
        return
    _cliente.create_score(
        trace_id=id_do_trace(response_id),
        name="resposta_incorreta",
        value=1.0,
        data_type="NUMERIC",
        comment=mascarar_dados_pessoais(detalhe) if detalhe else None,
    )
    _cliente.flush()


@contextmanager
def atributos_do_trace(**kwargs: Any) -> Iterator[None]:
    """Propaga atributos do trace (trace_name, tags, metadata, session_id) aos spans filhos."""
    if _propagar is None:
        yield
        return
    with _propagar(**kwargs):
        yield


def resumo_trechos(retrieved: List[Any]) -> List[Dict[str, Any]]:
    """Resumo compacto dos Trechos recuperados, sem o texto, para não inflar os traces."""
    resumo: List[Dict[str, Any]] = []
    for posicao, item in enumerate(retrieved, start=1):
        c = item.chunk
        resumo.append(
            {
                "posicao": posicao,
                "chunk_id": getattr(c, "chunk_id", None),
                "doc_id": c.doc_id,
                "pagina_pdf": getattr(c, "pagina_pdf", None),
                "evidencia": c.evidence_level,
                "bm25_rank": item.bm25_rank,
                "vector_rank": item.vector_rank,
                "rrf": item.rrf_score,
                "score_final": item.rerank_score,
            }
        )
    return resumo


def tipo_de_resposta(resposta: Any) -> str:
    """Caminho que produziu a resposta, para filtrar e contar no painel do Langfuse.

    "risco", "risco_llm", "prompt_injection" e "nao_sei" são respostas fixas; os demais valores são o
    `fundamentacao_status` da síntese (citação por frase, issue #12).
    """
    if resposta.risk_triggered:
        # Camada que acionou (#48): o léxico ou a camada LLM local.
        return "risco_llm" if getattr(resposta, "risk_layer", None) == "llm" else "risco"
    if resposta.prompt_injection_detected:
        return "prompt_injection"
    if resposta.fundamentacao_status:
        return resposta.fundamentacao_status
    if resposta.abstencao:
        return "nao_sei"
    return "outra"


def scores_da_resposta(resposta: Any) -> List[Tuple[str, Any, str]]:
    """Scores de cada trace: (nome, valor, tipo de dado do Langfuse).

    Os indicadores valem 0 ou 1, para que a média no painel seja a taxa. `citacoes_validas` só
    existe quando o LLM respondeu com citações (válidas ou bloqueadas pela checagem da #12).
    """
    tipo = tipo_de_resposta(resposta)
    scores: List[Tuple[str, Any, str]] = [
        ("tipo_resposta", tipo, "CATEGORICAL"),
        ("guardrail_lei_8234", 1.0 if resposta.guardrail_triggered else 0.0, "NUMERIC"),
        ("risco_acionado", 1.0 if resposta.risk_triggered else 0.0, "NUMERIC"),
        ("prompt_injection", 1.0 if resposta.prompt_injection_detected else 0.0, "NUMERIC"),
        ("nao_sei", 1.0 if resposta.abstencao else 0.0, "NUMERIC"),
        ("sintese_extrativa", 1.0 if tipo.startswith("extrativa") else 0.0, "NUMERIC"),
    ]
    if tipo in {"llm_citacoes_validas", "extrativa_apos_citacao_invalida"}:
        scores.append(("citacoes_validas", 1.0 if tipo == "llm_citacoes_validas" else 0.0, "NUMERIC"))
    return scores


def flush() -> None:
    """Envia o que estiver pendente. O SDK também faz isso ao encerrar o processo."""
    if _cliente is not None:
        _cliente.flush()
