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
# Benchmark v2 (issue #13): golden set com Trecho e página esperados, dev e test separados.
GOLDEN_V2_DIR = PROJECT_ROOT / "eval" / "golden" / "v2"
BENCHMARK_V2_REPORT_PATH = DATA_DIR / "benchmark" / "benchmark_v2_report.json"

# Caminhos do Corpus Curado (Catálogo Oficial manifest.yaml e JSONLs de RAG)
CORPUS_MANIFEST_PATH = PROJECT_ROOT / "corpus" / "manifest.yaml"
# Casos do detector de risco (RF-IA03), avaliados junto com o benchmark (issue #9).
RISCO_CASOS_PATH = PROJECT_ROOT / "eval" / "risco" / "casos.json"
# "Não sei" (RF-IA01, issue #6): limiar do cosseno do Trecho mais próximo no ChromaDB.
# Depende da escala do modelo de embeddings: recalibrado para o e5-large no dev de
# eval/abstencao/casos.json em 24/11/2026 (issue #15; era 0,40 com o MiniLM). Trocar o modelo exige
# recalibrar (src/evaluation/comparacao_embeddings.py; eval/runs/comparacao_embeddings_issue15.md).
ABSTENCAO_LIMIAR_COSSENO = float(os.getenv("ABSTENCAO_LIMIAR_COSSENO", "0.845"))
ABSTENCAO_CASOS_PATH = PROJECT_ROOT / "eval" / "abstencao" / "casos.json"
RISCO_HOLDOUT_PATH = PROJECT_ROOT / "eval" / "risco" / "holdout.json"
# Camada semântica do detector de risco (issue #48): modelo do Ollama local consultado quando o
# léxico não aciona. Por decisão da equipe (20/11/2026), é o mesmo modelo da síntese (OLLAMA_MODEL,
# ADR 0004): dois modelos não cabem juntos numa GPU de 8 GB, e a troca a cada pergunta estouraria o
# limite de tempo. Medição em eval/risco/llm_resultados.md. Vazio desliga a camada. Só roda com o
# Ollama habilitado (enable_ollama), então o benchmark e o CI, sem LLM, medem só o léxico. O limite
# de tempo vale por chamada (RNF29: p95 <= 3 s); se estourar ou o Ollama falhar, vale só o léxico.
RISCO_LLM_MODELO = os.getenv("RISCO_LLM_MODELO", os.getenv("OLLAMA_MODEL", "gemma4:e4b"))
RISCO_LLM_TIMEOUT = float(os.getenv("RISCO_LLM_TIMEOUT", "3.0"))
# Nível de preocupação (0 a 10) a partir do qual a camada LLM aciona. 1 = qualquer sinal; escolhido
# só com o desenvolvimento e as perguntas comuns (eval/risco/llm_criterios.md, adendo 2).
RISCO_LLM_LIMIAR = int(os.getenv("RISCO_LLM_LIMIAR", "1"))
CORPUS_RAG_DIR = PROJECT_ROOT / "corpus" / "nutricao" / "rag"
TRACEABILITY_DB_PATH = Path(os.getenv("CULTIVA_TRACEABILITY_DB", str(DATA_DIR / "traceability.sqlite3")))

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
# Modelo local do fastembed (ADR 0005, issue #15). Escolhido na comparação com o MiniLM-L12 e o
# mpnet multilíngues: eval/runs/comparacao_embeddings_issue15.md. Trocar o modelo muda a escala do
# cosseno: recalibre ABSTENCAO_LIMIAR_COSSENO junto.
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "intfloat/multilingual-e5-large")
# Com "true" (padrão), o texto vai ao modelo de embeddings em minúsculas e sem acentos, como no
# BM25. A dimensão dos vetores vem do próprio modelo (catálogo do fastembed).
EMBEDDING_NORMALIZAR_TEXTO = os.getenv("EMBEDDING_NORMALIZAR_TEXTO", "true").strip().lower() in {
    "1", "true", "sim", "yes"
}
# Cache dos vetores dos Trechos, por modelo e texto (issue #15): só Trechos novos ou alterados são
# recalculados ao refazer uma coleção. Vazio desliga o cache.
_cache_vetores = os.getenv("EMBEDDING_CACHE_PATH", str(DATA_DIR / "vector_store" / "vetores_cache.sqlite3")).strip()
EMBEDDING_CACHE_PATH = Path(_cache_vetores) if _cache_vetores else None
# Parâmetros do índice HNSW do ChromaDB. Com os padrões, a busca aproximada perdia vizinhos
# e variava a cada carga do índice; com 200, o top-24 coincide com a busca exata no corpus atual.
HNSW_EF_CONSTRUCTION = int(os.getenv("HNSW_EF_CONSTRUCTION", "200"))
HNSW_EF_SEARCH = int(os.getenv("HNSW_EF_SEARCH", "200"))

# Provedor de LLM ("groq", "ollama" ou "auto")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama").lower()
ALLOW_EXTERNAL_LLM = os.getenv("ALLOW_EXTERNAL_LLM", "false").strip().lower() in (
    "1",
    "true",
    "sim",
    "yes",
)

# Configurações da API Gratuita Groq (https://console.groq.com)
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_BASE_URL = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
GROQ_FALLBACK_MODEL = os.getenv("GROQ_FALLBACK_MODEL", "qwen/qwen3.8-27b")
GROQ_TIMEOUT = float(os.getenv("GROQ_TIMEOUT", "30.0"))

# Configurações do Modelo Local (Ollama - Fallback Opcional)
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
# Modelo principal e reserva escolhidos por medição na issue #55 (ADR 0004).
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma4:e4b")
OLLAMA_FALLBACK_MODEL = os.getenv("OLLAMA_FALLBACK_MODEL", "qwen2.5:7b")
# Condições da medição do ADR 0004: contexto de 8192 tokens e modo de raciocínio desligado (modelos
# que raciocinam por padrão, como o qwen3.5, multiplicam a latência). A saída vai até 2048 tokens:
# com 1024, o gemma4:e4b truncava o JSON da citação por frase (issue #12) em 3 de 30 casos do dev.
OLLAMA_NUM_CTX = int(os.getenv("OLLAMA_NUM_CTX", "8192"))
OLLAMA_NUM_PREDICT = int(os.getenv("OLLAMA_NUM_PREDICT", "2048"))
OLLAMA_THINK = os.getenv("OLLAMA_THINK", "false").strip().lower() in {"1", "true", "sim", "yes"}
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

# Ranking (issue #35). A ablação mostrou que a sobreposição de termos (0,25) e o bônus de
# evidência pesavam cerca de 10 vezes a fusão RRF e decidiam o ranking sozinhos; a mistura
# densa com TF-IDF/LSA também não ajudava. Padrão: RRF puro sobre BM25 + ChromaDB.
# Detalhes e números: eval/runs/ablacao_mrr_issue35.md.
# MODO_DENSO: "chromadb_pure" (só ChromaDB), "chromadb_dense" (ChromaDB + TF-IDF/LSA) ou "legacy_lsa".
MODO_DENSO = os.getenv("MODO_DENSO", "chromadb_pure")
RERANK_PESO_SOBREPOSICAO = float(os.getenv("RERANK_PESO_SOBREPOSICAO", "0.0"))
RERANK_BONUS_EVIDENCIA = os.getenv("RERANK_BONUS_EVIDENCIA", "false").strip().lower() in {"1", "true", "sim"}

# Observabilidade (proposta técnica, ainda não documentada na Documentacao-Cultiva; ADR 0003).
# Desligada por padrão: só envia traces ao Langfuse com CULTIVA_LANGFUSE=true e as chaves
# LANGFUSE_PUBLIC_KEY e LANGFUSE_SECRET_KEY definidas. O destino padrão é um Langfuse local
# (LANGFUSE_BASE_URL=http://localhost:3000), e não a nuvem, que é o padrão do SDK: servidor fora
# desta máquina, inclusive auto-hospedado pela equipe, exige ALLOW_EXTERNAL_LANGFUSE=true, como o
# ALLOW_EXTERNAL_LLM faz para a Groq. Sem essa liberação, o Langfuse fica desligado.
LANGFUSE_BASE_URL = (
    os.getenv("LANGFUSE_BASE_URL") or os.getenv("LANGFUSE_HOST") or "http://localhost:3000"
).strip()
ALLOW_EXTERNAL_LANGFUSE = os.getenv("ALLOW_EXTERNAL_LANGFUSE", "false").strip().lower() in {
    "1", "true", "sim", "yes"
}
# Versão do código registrada em cada trace (campo "release" do Langfuse). Sem a variável, usa o
# commit atual do Git, para comparar traces de antes e depois de um merge.
LANGFUSE_RELEASE = os.getenv("LANGFUSE_RELEASE", "").strip()


def destino_local(url: str) -> bool:
    """O endereço aponta para esta máquina (loopback)?"""
    from urllib.parse import urlparse

    return (urlparse(url).hostname or "").lower() in {"localhost", "127.0.0.1", "::1"}


LANGFUSE_PEDIDO = (
    os.getenv("CULTIVA_LANGFUSE", "false").strip().lower() in {"1", "true", "sim", "yes"}
    and bool(os.getenv("LANGFUSE_PUBLIC_KEY", "").strip())
    and bool(os.getenv("LANGFUSE_SECRET_KEY", "").strip())
)


def langfuse_liberado(pedido: bool, url: str, permitir_externo: bool) -> bool:
    """Liga o Langfuse só se foi pedido e o destino é local ou o envio externo foi liberado."""
    return pedido and (destino_local(url) or permitir_externo)


LANGFUSE_ATIVO = langfuse_liberado(LANGFUSE_PEDIDO, LANGFUSE_BASE_URL, ALLOW_EXTERNAL_LANGFUSE)
