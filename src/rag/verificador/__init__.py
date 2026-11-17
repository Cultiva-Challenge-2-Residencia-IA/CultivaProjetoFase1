"""Módulo Verificador: grafo de conhecimento de 4 camadas e citações por frase (issue #12)."""

from src.rag.verificador.citacoes import VerificacaoCitacoes, verificar_citacoes
from src.rag.verificador.graph_verifier import GraphClinicalVerifier
from src.retrieval.graph_engine import CausalKnowledgeGraphEngine

__all__ = ["CausalKnowledgeGraphEngine", "GraphClinicalVerifier", "VerificacaoCitacoes", "verificar_citacoes"]
