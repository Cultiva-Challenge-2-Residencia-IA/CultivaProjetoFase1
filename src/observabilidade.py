"""Observabilidade opcional com Langfuse.

Proposta técnica, ainda não documentada na Documentacao-Cultiva. Quando
`LANGFUSE_ATIVO` é falso (padrão, inclusive no CI), o Langfuse nem é importado e
todas as funções daqui viram no-ops, então o benchmark e os testes não mudam.

Uso:

    with observacao("retrieve", tipo="retriever", input={"query": q}) as obs:
        ...
        obs.update(output=resumo)
"""

from contextlib import contextmanager
from typing import Any, Dict, Iterator, List

from src.config import LANGFUSE_ATIVO

_cliente: Any = None
_propagar: Any = None

if LANGFUSE_ATIVO:
    from langfuse import get_client, propagate_attributes

    _cliente = get_client()
    _propagar = propagate_attributes


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
def observacao(nome: str, tipo: str = "span", **kwargs: Any) -> Iterator[Any]:
    """Abre uma observação aninhada à atual (span, generation, retriever, tool, guardrail...)."""
    if _cliente is None:
        yield _ObservacaoNula()
        return
    with _cliente.start_as_current_observation(name=nome, as_type=tipo, **kwargs) as obs:
        yield obs


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


def flush() -> None:
    """Envia o que estiver pendente. O SDK também faz isso ao encerrar o processo."""
    if _cliente is not None:
        _cliente.flush()
