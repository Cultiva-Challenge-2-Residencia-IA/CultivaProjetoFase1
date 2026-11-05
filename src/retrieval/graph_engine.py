import json
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

import networkx as nx

from src.config import KNOWLEDGE_GRAPH_PATH
from src.models.schemas import CausalGraphPath
from src.retrieval.hybrid_retriever import normalize_text, tokenize_biomedical

GRADE_PRIORITY = {
    "GRADE_A": 4,
    "GUIDELINE_CONSENSUS": 3,
    "GRADE_B": 2,
    "GRADE_C": 1,
}


class CausalKnowledgeGraphEngine:
    """
    Motor de Grafo de Conhecimento Controlado em 4 Camadas (Passo 3 - NetworkX):
      Camada 1 (FOOD: Alimento/Grupo TACO & FoodOn)
         └──[CONTAINS]──> Camada 2 (COMPOUND: Nutriente/Composto Bioativo FooDB & TACO)
                            └──[TRIGGERS_MECHANISM]──> Camada 3 (MECHANISM: Via Fisiológica)
                                                         └──[CAUSES_EFFECT (PICO/GRADE)]──> Camada 4 (OUTCOME: Desfecho Clínico)
    """

    def __init__(self, graph_json_path: Path = KNOWLEDGE_GRAPH_PATH) -> None:
        if not graph_json_path.exists():
            raise FileNotFoundError(
                f"Arquivo do Grafo de 4 Camadas não encontrado em: {graph_json_path}"
            )

        raw_paths: List[Dict[str, Any]] = json.loads(
            graph_json_path.read_text(encoding="utf-8")
        )
        self.paths: List[CausalGraphPath] = [
            CausalGraphPath.model_validate(item) for item in raw_paths
        ]
        self.graph = nx.MultiDiGraph()
        self._build_4layer_networkx_graph()

    def _build_4layer_networkx_graph(self) -> None:
        for p in self.paths:
            f_id = f"food:{p.food_node}"
            c_id = f"compound:{p.compound_node}"
            m_id = f"mechanism:{p.mechanism_node}"
            o_id = f"outcome:{p.outcome_node}"

            self.graph.add_node(f_id, layer="FOOD", label=p.food_node)
            self.graph.add_node(
                c_id,
                layer="COMPOUND",
                label=p.compound_node,
                concentration=p.compound_concentration_info,
            )
            self.graph.add_node(m_id, layer="MECHANISM", label=p.mechanism_node)
            self.graph.add_node(o_id, layer="OUTCOME", label=p.outcome_node)

            self.graph.add_edge(
                f_id,
                c_id,
                key=p.path_id,
                relation="CONTAINS",
                concentration=p.compound_concentration_info,
            )
            self.graph.add_edge(
                c_id,
                m_id,
                key=p.path_id,
                relation="TRIGGERS_MECHANISM",
            )
            self.graph.add_edge(
                m_id,
                o_id,
                key=p.path_id,
                relation="CAUSES_EFFECT",
                path_id=p.path_id,
                effect_direction=p.effect_direction,
                relationship_nature=p.relationship_nature,
                evidence_grade=p.evidence_grade,
                studied_protocol=p.studied_protocol,
                contraindications=p.contraindications,
                source_reference=p.source_reference,
            )

    def get_graph_stats(self) -> Dict[str, int]:
        layers = {"FOOD": 0, "COMPOUND": 0, "MECHANISM": 0, "OUTCOME": 0}
        for _, data in self.graph.nodes(data=True):
            layer = data.get("layer")
            if layer in layers:
                layers[layer] += 1
        return {
            "total_nodes": self.graph.number_of_nodes(),
            "total_edges": self.graph.number_of_edges(),
            "total_causal_paths": len(self.paths),
            **layers,
        }

    def _detect_query_restrictions(self, norm_query: str) -> Set[str]:
        restrictions: Set[str] = set()
        if any(
            kw in norm_query
            for kw in [
                "doenca renal",
                "renal cronica",
                "drc",
                "nao aumente o potassio",
                "sem aumentar o potassio",
                "hipercalemia",
                "restricao de potassio",
            ]
        ):
            restrictions.add("renal_potassium")
        if "anticoagulante" in norm_query or "calculo biliar" in norm_query:
            restrictions.add("biliary_anticoagulant")
        return restrictions

    def traverse_for_query(
        self, user_query: str, max_paths: int = 4
    ) -> Tuple[List[CausalGraphPath], str]:
        """
        Percorre o Grafo de 4 Camadas no NetworkX buscando cadeias completas
        (Alimento -> Composto -> Mecanismo -> Desfecho) relevantes para a consulta,
        aplicando filtro de contraindicações e diferenciação entre efeito in vitro vs. ECR.
        """
        norm_q = normalize_text(user_query)
        query_tokens = set(tokenize_biomedical(user_query))
        if not query_tokens:
            return [], ""

        restrictions = self._detect_query_restrictions(norm_q)
        scored_paths: List[Tuple[float, CausalGraphPath]] = []

        # Reconstrói os caminhos de 4 camadas diretamente por travessia no MultiDiGraph do NetworkX
        for f_node, f_data in self.graph.nodes(data=True):
            if f_data.get("layer") != "FOOD":
                continue
            for _, c_node, k1, e1 in self.graph.out_edges(f_node, keys=True, data=True):
                for _, m_node, k2, e2 in self.graph.out_edges(c_node, keys=True, data=True):
                    if k2 != k1:
                        continue
                    for _, o_node, k3, e3 in self.graph.out_edges(
                        m_node, keys=True, data=True
                    ):
                        if k3 != k1:
                            continue

                        path_obj = next(
                            (p.model_copy(deep=True) for p in self.paths if p.path_id == k3),
                            None,
                        )
                        if path_obj is None:
                            continue

                        full_path_text = (
                            f"{path_obj.food_node} {path_obj.compound_node} "
                            f"{path_obj.compound_concentration_info} {path_obj.mechanism_node} "
                            f"{path_obj.outcome_node} {path_obj.studied_protocol} "
                            f"{' '.join(path_obj.contraindications)}"
                        )
                        path_tokens = set(tokenize_biomedical(full_path_text))
                        overlap = len(query_tokens.intersection(path_tokens))
                        if overlap == 0:
                            continue

                        score = overlap / max(len(query_tokens), 1)
                        score += 0.02 * GRADE_PRIORITY.get(path_obj.evidence_grade, 1)

                        # Bônus de precisão para casamento direto nos nós de Alimento, Composto ou Desfecho
                        core_nodes_norm = normalize_text(
                            f"{path_obj.food_node} {path_obj.compound_node} {path_obj.outcome_node}"
                        )
                        core_tokens = set(tokenize_biomedical(core_nodes_norm))
                        core_overlap = len(query_tokens.intersection(core_tokens))
                        score += 0.15 * core_overlap

                        # Verifica contraindicações para condições restritivas (ex: Doença Renal + Potássio)
                        contra_norm = normalize_text(" ".join(path_obj.contraindications))
                        if "renal_potassium" in restrictions:
                            if "renal" in contra_norm or "hipercalemia" in contra_norm:
                                path_obj.is_contraindicated_for_query = True
                                score += 0.15  # Mantém visível com alerta explícito de contraindicação
                            elif "seguranca na doenca renal" in normalize_text(
                                path_obj.outcome_node
                            ) or "sem elevar potassio" in normalize_text(
                                path_obj.mechanism_node
                            ):
                                score += 0.35  # Impulsiona as alternativas seguras para DRC!

                        scored_paths.append((score, path_obj))

        scored_paths.sort(key=lambda pair: pair[0], reverse=True)
        selected = [p for _, p in scored_paths[:max_paths]]
        if not selected:
            return [], ""

        lines = [
            "CAMINHOS DO GRAFO CAUSAL DE 4 CAMADAS (NetworkX: Alimento ➔ Composto ➔ Mecanismo ➔ Desfecho GRADE):"
        ]
        for p in selected:
            status_tag = (
                "⚠️ [CONTRAINDICADO / CAUTELA NA CONDIÇÃO INFORMADA]"
                if p.is_contraindicated_for_query
                else f"✅ [{p.evidence_grade} | {p.relationship_nature}]"
            )
            contra_str = (
                f" | Contraindicações/Cautelas: {'; '.join(p.contraindications)}"
                if p.contraindications
                else ""
            )
            lines.append(
                f"- {status_tag} [1. Alimento: {p.food_node}] ➔ "
                f"[2. Composto: {p.compound_node} ({p.compound_concentration_info})] ➔ "
                f"[3. Mecanismo: {p.mechanism_node}] ➔ "
                f"[4. Desfecho ({p.effect_direction}): {p.outcome_node}] | "
                f"Protocolo: {p.studied_protocol}{contra_str}"
            )

        return selected, "\n".join(lines)
