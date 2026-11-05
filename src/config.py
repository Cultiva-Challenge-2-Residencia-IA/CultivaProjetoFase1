import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
GUIDELINES_DIR = DATA_DIR / "raw" / "guidelines"
GUIDELINES_PATH = GUIDELINES_DIR / "guia_alimentar_ms_2ed.json"
TACO_RAW_PATH = DATA_DIR / "raw" / "taco" / "taco_raw.json"
KNOWLEDGE_GRAPH_PATH = DATA_DIR / "raw" / "knowledge_graph" / "nutrition_4layer_graph.json"
BENCHMARK_QUESTIONS_PATH = DATA_DIR / "benchmark" / "eval_questions.json"
BENCHMARK_REPORT_PATH = DATA_DIR / "benchmark" / "baseline_report.json"

# Configurações do Modelo Local (Ollama)
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
OLLAMA_FALLBACK_MODEL = os.getenv("OLLAMA_FALLBACK_MODEL", "qwen2.5:3b")
OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "45.0"))

# Backend de vetorização local ("local_lsa" ou "ollama")
VECTOR_BACKEND = os.getenv("VECTOR_BACKEND", "local_lsa")

# Parâmetros do Motor RAG Híbrido (Fase 1 Baseline)
TOP_K_BM25 = int(os.getenv("TOP_K_BM25", "8"))
TOP_K_VECTOR = int(os.getenv("TOP_K_VECTOR", "8"))
RRF_K = int(os.getenv("RRF_K", "60"))
WEIGHT_BM25 = float(os.getenv("WEIGHT_BM25", "0.55"))
WEIGHT_VECTOR = float(os.getenv("WEIGHT_VECTOR", "0.45"))
TOP_K_FINAL = int(os.getenv("TOP_K_FINAL", "4"))
MAX_CHUNKS_PER_DOC = int(os.getenv("MAX_CHUNKS_PER_DOC", "2"))
