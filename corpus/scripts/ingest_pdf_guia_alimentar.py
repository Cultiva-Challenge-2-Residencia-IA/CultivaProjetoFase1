"""Script de ingestão do PDF oficial do Guia Alimentar para a População Brasileira (2ª Edição)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.ingestion.pdf_ingestor import ingest_guia_alimentar_pdf

if __name__ == "__main__":
    docs = ingest_guia_alimentar_pdf()
    print(f"Ingestão concluída: {len(docs)} documentos extraídos do Guia Alimentar MS.")
