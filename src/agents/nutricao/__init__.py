"""Agente Consultor Científico de Nutrição Baseado em Evidências (RAG Híbrido + TACO + Grafo 4 Camadas)."""

from src.agent.consultant_baseline import NutritionConsultantBaseline
from src.agent.llm_client import SYSTEM_PROMPT_CONSULTANT, LocalLLMClient

__all__ = [
    "NutritionConsultantBaseline",
    "LocalLLMClient",
    "SYSTEM_PROMPT_CONSULTANT",
]
