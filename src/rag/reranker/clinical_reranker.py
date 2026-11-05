"""Módulo Reranker Clínico baseado em cobertura conceitual, nível GRADE e diversificação documental."""

from typing import List
from src.config import MAX_CHUNKS_PER_DOC, TOP_K_FINAL
from src.models.schemas import RetrievedChunk
from src.retrieval.hybrid_retriever import EVIDENCE_GRADE_BONUS, tokenize_biomedical


class ClinicalEvidenceReranker:
    """Reordena chunks recuperados priorizando evidência GRADE_A/GUIDELINE_CONSENSUS e diversificando fontes."""

    def __init__(self, max_chunks_per_doc: int = MAX_CHUNKS_PER_DOC) -> None:
        self.max_chunks_per_doc = max_chunks_per_doc

    def compute_clinical_bonus(self, query: str, chunk: RetrievedChunk) -> float:
        query_tokens = set(tokenize_biomedical(query))
        chunk_tokens = set(tokenize_biomedical(chunk.chunk.contextualized_text))
        overlap = len(query_tokens.intersection(chunk_tokens)) / max(len(query_tokens), 1)
        grade_bonus = EVIDENCE_GRADE_BONUS.get(chunk.chunk.evidence_level, 0.0)
        return (0.20 * overlap) + grade_bonus

    def diversify(
        self, ranked_chunks: List[RetrievedChunk], top_k: int = TOP_K_FINAL
    ) -> List[RetrievedChunk]:
        selected: List[RetrievedChunk] = []
        doc_counts: dict[str, int] = {}
        for item in ranked_chunks:
            doc_id = item.chunk.doc_id
            if doc_counts.get(doc_id, 0) >= self.max_chunks_per_doc:
                continue
            selected.append(item)
            doc_counts[doc_id] = doc_counts.get(doc_id, 0) + 1
            if len(selected) >= top_k:
                break
        return selected
