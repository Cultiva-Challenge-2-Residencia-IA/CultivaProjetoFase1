"""Módulo Retriever Híbrido (BM25 + Vetorial SVD + Fusão RRF) e Ferramenta Determinística Tabela TACO."""

from src.retrieval.hybrid_retriever import (
    CLINICAL_SYNONYMS,
    EVIDENCE_GRADE_BONUS,
    HybridRetriever,
    expand_clinical_synonyms,
    normalize_text,
    tokenize_biomedical,
)
from src.retrieval.taco_tool import TacoDeterministicTool
from src.retrieval.vector_store import DenseMultilingualEmbedder, NutritionVectorStore

__all__ = [
    "HybridRetriever",
    "NutritionVectorStore",
    "DenseMultilingualEmbedder",
    "TacoDeterministicTool",
    "CLINICAL_SYNONYMS",
    "EVIDENCE_GRADE_BONUS",
    "expand_clinical_synonyms",
    "normalize_text",
    "tokenize_biomedical",
]
