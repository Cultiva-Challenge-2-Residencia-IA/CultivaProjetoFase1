"""Análise Exploratória de Dados (EDA) do Corpus Científico, Tabela TACO (597 alimentos) e Grafo de 4 Camadas."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.config import GUIDELINES_DIR
from src.ingestion.contextual_chunker import ContextualChunker
from src.retrieval.graph_engine import CausalKnowledgeGraphEngine
from src.retrieval.taco_tool import TacoDeterministicTool


def run_eda_summary() -> dict:
    chunker = ContextualChunker()
    chunks = chunker.load_and_chunk_directory(GUIDELINES_DIR)
    taco = TacoDeterministicTool()
    graph = CausalKnowledgeGraphEngine()

    return {
        "total_chunks": len(chunks),
        "unique_documents": len({c.doc_id for c in chunks}),
        "taco_total_foods": len(taco.foods),
        "taco_categories": sorted({str(f.get("category", "")) for f in taco.foods}),
        "graph_stats": graph.get_graph_stats(),
    }


if __name__ == "__main__":
    stats = run_eda_summary()
    print("=== EDA DO PROJETO NUTRI-EVIDENCE-CONSULTANT ===")
    for k, v in stats.items():
        print(f"- {k}: {v}")
