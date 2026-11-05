"""Verificador de Sinergia de Biodisponibilidade e Contraindicação Clínica no Grafo de 4 Camadas."""

from typing import List, Tuple
from src.models.schemas import CausalGraphPath
from src.retrieval.graph_engine import CausalKnowledgeGraphEngine


class GraphClinicalVerifier:
    """Valida se as rotas recuperadas apresentam alertas de baixa eficácia isolada ou contraindicações clínicas."""

    def __init__(self, graph_engine: CausalKnowledgeGraphEngine | None = None) -> None:
        self.engine = graph_engine or CausalKnowledgeGraphEngine()

    def verify_query_paths(self, query: str, max_paths: int = 4) -> Tuple[List[CausalGraphPath], List[str]]:
        paths, _ = self.engine.traverse_for_query(query, max_paths=max_paths)
        warnings: List[str] = []
        for p in paths:
            if p.is_contraindicated_for_query:
                warnings.append(
                    f"CONTRAINDICAÇÃO DETECTADA para '{p.food_node}': {'; '.join(p.contraindications)}"
                )
            elif p.effect_direction == "LOW_EFFICACY_ALONE":
                warnings.append(
                    f"ALERTA DE BIODISPONIBILIDADE para '{p.compound_node}': baixa eficácia isolada sem sinergia culinária."
                )
        return paths, warnings
