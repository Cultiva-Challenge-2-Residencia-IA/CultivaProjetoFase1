"""Script de coleta de Meta-Análises e Revisões Sistemáticas reais via API NCBI Entrez / PubMed."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.ingestion.pubmed_ingestor import fetch_and_save_pubmed_corpus

if __name__ == "__main__":
    docs = fetch_and_save_pubmed_corpus()
    print(f"Coleta PubMed concluída: {len(docs)} documentos clínicos salvos.")
