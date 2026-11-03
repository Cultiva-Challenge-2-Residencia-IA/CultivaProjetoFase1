"""Busca por palavras em memória (estilo BM25), determinística e sem embeddings."""

import math
import re
from collections import Counter

from dominio.modelos import Trecho
from dominio.texto import normalizar

_STOPWORDS = frozenset(
    """
    a o as os um uma uns umas de do da dos das em no na nos nas por para pra com sem
    e ou mas que se ao aos como mais menos muito pouco ja nao sim eu voce ele ela nos
    meu minha seu sua isso isto esse essa este esta ser estar ter fazer qual quais
    quando onde porque por que qual e sao foi tem pode posso devo deve sobre ate entre
    """.split()  # noqa: SIM905 (lista legível de stopwords)
)


def tokenizar(texto: str) -> list[str]:
    termos = re.findall(r"[a-z0-9]+", normalizar(texto))
    return [_radical(t) for t in termos if t not in _STOPWORDS and len(t) > 2]


def _radical(termo: str) -> str:
    """Reduz plurais simples para aproximar "alimentos" de "alimento"."""
    for sufixo in ("oes", "aes", "s"):
        if termo.endswith(sufixo) and len(termo) > len(sufixo) + 3:
            return termo[: -len(sufixo)]
    return termo


class BuscaPorPalavras:
    def __init__(self, trechos: tuple[Trecho, ...], k1: float = 1.5, b: float = 0.75):
        self._trechos = trechos
        self._docs = [Counter(tokenizar(t.texto)) for t in trechos]
        self._tamanhos = [sum(d.values()) for d in self._docs]
        self._media = sum(self._tamanhos) / max(len(self._docs), 1)
        n = len(self._docs)
        df = Counter(termo for d in self._docs for termo in d)
        self._idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}
        self._k1, self._b = k1, b

    @property
    def ids(self) -> frozenset[str]:
        return frozenset(t.id for t in self._trechos)

    def buscar(self, consulta: str, k: int = 3) -> list[Trecho]:
        termos = tokenizar(consulta)
        pontuados = []
        for trecho, doc, tamanho in zip(self._trechos, self._docs, self._tamanhos, strict=True):
            pontos = 0.0
            for termo in termos:
                f = doc.get(termo, 0)
                if f:
                    norma = self._k1 * (1 - self._b + self._b * tamanho / self._media)
                    pontos += self._idf[termo] * f * (self._k1 + 1) / (f + norma)
            if pontos > 0:
                pontuados.append((pontos, trecho))
        pontuados.sort(key=lambda par: par[0], reverse=True)
        return [trecho for _, trecho in pontuados[:k]]
