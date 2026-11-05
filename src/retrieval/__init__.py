"""Módulo de recuperação híbrida (BM25 + Vetorial Local + RRF + Reranker) para a aba Nutrição."""

from src.retrieval.hybrid_retriever import (
    CLINICAL_SYNONYMS,
    EVIDENCE_GRADE_BONUS,
    HybridRetriever,
    expand_clinical_synonyms,
    normalize_text,
    tokenize_biomedical,
)
from src.retrieval.nutricao_retriever import (
    NutricaoHybridRetriever,
    NutricaoRetrieverProtocol,
)
from src.retrieval.taco_tool import TacoDeterministicTool

__all__ = [
    "HybridRetriever",
    "NutricaoHybridRetriever",
    "NutricaoRetrieverProtocol",
    "TacoDeterministicTool",
    "CLINICAL_SYNONYMS",
    "EVIDENCE_GRADE_BONUS",
    "expand_clinical_synonyms",
    "normalize_text",
    "tokenize_biomedical",
]
