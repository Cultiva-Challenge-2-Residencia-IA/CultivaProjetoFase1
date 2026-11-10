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

# Caminhos do Corpus Curado (Catálogo Oficial manifest.yaml e JSONLs de RAG)
CORPUS_MANIFEST_PATH = PROJECT_ROOT / "corpus" / "manifest.yaml"
# Casos do detector de risco (RF-IA03), avaliados junto com o benchmark (issue #9).
RISCO_CASOS_PATH = PROJECT_ROOT / "eval" / "risco" / "casos.json"
RISCO_HOLDOUT_PATH = PROJECT_ROOT / "eval" / "risco" / "holdout.json"
# Limiar da camada de similaridade do detector de risco (cosseno com o exemplo mais próximo).
# Calibrado em 10/11/2026: 0 de 58 perguntas comuns dos benchmarks acionam; ver src/guardrails/risco/exemplos.yaml.
RISCO_LIMIAR_SIMILARIDADE = float(os.getenv("RISCO_LIMIAR_SIMILARIDADE", "0.62"))
CORPUS_RAG_DIR = PROJECT_ROOT / "corpus" / "nutricao" / "rag"

# Gate de aprovação (ADR 0002, issue #7): por padrão só fontes com approval_status
# "aprovado" entram no índice. A flag de desenvolvimento inclui também as "pendente".
INCLUDE_PENDING_SOURCES = os.getenv("CULTIVA_INCLUIR_PENDENTES", "false").strip().lower() in (
    "1",
    "true",
    "sim",
    "yes",
)

# Configurações do Banco Vetorial Persistente (ChromaDB) e Modelo de Embeddings
VECTOR_STORE_DIR = DATA_DIR / "vector_store" / "chroma_db"
VECTOR_COLLECTION_NAME = os.getenv(
    "VECTOR_COLLECTION_NAME", "cultiva_nutricao_evidencias"
)
EMBEDDING_MODEL_NAME = os.getenv(
    "EMBEDDING_MODEL_NAME",
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
)
EMBEDDING_DIMENSION = int(os.getenv("EMBEDDING_DIMENSION", "384"))
# Parâmetros do índice HNSW do ChromaDB. Com os padrões, a busca aproximada perdia vizinhos
# e variava a cada carga do índice; com 200, o top-24 coincide com a busca exata no corpus atual.
HNSW_EF_CONSTRUCTION = int(os.getenv("HNSW_EF_CONSTRUCTION", "200"))
HNSW_EF_SEARCH = int(os.getenv("HNSW_EF_SEARCH", "200"))

# Provedor de LLM ("groq", "ollama" ou "auto")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "groq").lower()

# Configurações da API Gratuita Groq (https://console.groq.com)
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_BASE_URL = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
GROQ_FALLBACK_MODEL = os.getenv("GROQ_FALLBACK_MODEL", "qwen/qwen3.8-27b")
GROQ_TIMEOUT = float(os.getenv("GROQ_TIMEOUT", "30.0"))

# Configurações do Modelo Local (Ollama - Fallback Opcional)
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
