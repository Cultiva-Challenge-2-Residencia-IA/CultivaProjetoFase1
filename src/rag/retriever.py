from __future__ import annotations

import math
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from src.rag.chunking import Chunk


@dataclass(frozen=True)
class RetrievalResult:
    chunk_id: str
    source_id: str
    score_dense: float
    score_lexical: float
    rrf_score: float


class Embedder:
    """Simple deterministic embedder for the nutritional corpus in tests and local dev."""

    @staticmethod
    def tokenize(text: str) -> list[str]:
        return [token for token in re.findall(r"[\wçáàãéèêíìóòõúùüñ]+", text.lower()) if token]

    @staticmethod
    def similarity(query: str, text: str) -> float:
        query_tokens = Embedder.tokenize(query)
        text_tokens = Embedder.tokenize(text)
        if not query_tokens or not text_tokens:
            return 0.0

        q_set = set(query_tokens)
        t_set = set(text_tokens)
        overlap = len(q_set & t_set)
        if overlap == 0:
            return 0.0
        return overlap / max(len(q_set), len(t_set))


class InMemoryVectorStore:
    def __init__(self, chunks: Iterable[Chunk]):
        self.chunks = list(chunks)

    def search(self, query: str, top_k: int = 5) -> list[RetrievalResult]:
        if not self.chunks:
            return []

        query_tokens = set(Embedder.tokenize(query))
        scored: list[tuple[Chunk, float, float]] = []

        for chunk in self.chunks:
            chunk_tokens = set(Embedder.tokenize(chunk.text))
            if not query_tokens:
                dense_score = 0.0
            else:
                dense_score = len(query_tokens & chunk_tokens) / max(len(query_tokens), len(chunk_tokens), 1)

            if not query_tokens:
                lexical_score = 0.0
            else:
                lexical_score = sum(1 for token in sorted(query_tokens) if token in chunk_tokens) / max(len(query_tokens), 1)

            scored.append((chunk, dense_score, lexical_score))

        scored.sort(key=lambda item: (item[1] + item[2], item[0].chunk_id), reverse=True)
        results: list[RetrievalResult] = []
        for chunk, dense_score, lexical_score in scored[:top_k]:
            rrf_score = min(1.0, dense_score + lexical_score)
            results.append(
                RetrievalResult(
                    chunk_id=chunk.chunk_id,
                    source_id=chunk.source_id,
                    score_dense=dense_score,
                    score_lexical=lexical_score,
                    rrf_score=rrf_score,
                )
            )

        return results


def hybrid_search(store: InMemoryVectorStore, query: str, top_k: int = 5) -> list[RetrievalResult]:
    return store.search(query, top_k=top_k)


class EvidenceGate:
    def __init__(self, min_score: float = 0.5):
        self.min_score = float(min_score)

    def can_answer(self, results: Sequence[RetrievalResult] | None) -> bool:
        if not results:
            return False
        top_result = results[0]
        return float(top_result.rrf_score) >= self.min_score or float(top_result.score_dense) >= self.min_score

    def reason(self, results: Sequence[RetrievalResult] | None) -> str:
        if not results or not self.can_answer(results):
            return "não sei"
        return "evidência suficiente"
