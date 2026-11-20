"""Imprime o diagrama Mermaid do grafo do orquestrador, com o subgrafo de cada agente expandido.

uv run python -m src.orquestrador
"""

from unittest.mock import MagicMock

from src.agents.nutricao.grafo import construir_subgrafo
from src.orquestrador.grafo import construir_grafo


def diagrama_mermaid() -> str:
    # O desenho só depende dos nós e das arestas, então o consultor pode ser um substituto vazio.
    grafo = construir_grafo({"nutricao": construir_subgrafo(MagicMock())}, MagicMock(), "nutricao")
    return grafo.get_graph(xray=True).draw_mermaid()


if __name__ == "__main__":
    print(diagrama_mermaid())
