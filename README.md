# CultivaProjetoFase1 — Módulo de Nutrição Baseada em Evidências (`rag-hibrido`)

Projeto: **CULTIVA**, um aplicativo que usa IA para ajudar jovens adultos e estudantes (18+) a transformar bons hábitos em decisões simples e sustentáveis, sem substituir o profissional de saúde. Alinhado aos ODS 3 (Saúde e Bem-Estar) e 4 (Educação de Qualidade).

📄 **Documentação Completa da Entrega (Artefatos, Chunking, Embeddings, Banco Vetorial, Arquitetura e Ingestão):**
👉 Consulte [`docs/entrega-rag-nutricao.md`](docs/entrega-rag-nutricao.md)

---

## Consultor Científico de Nutrição Baseado em Evidências (RAG Híbrido + ChromaDB + TACO + Grafo Causal)

Implementação completa de um consultor de nutrição baseado em evidências científicas e diretrizes oficiais, operando com **Banco Vetorial Persistente (`ChromaDB` + Embeddings Multilíngues de 384d)**, **API gratuita da Groq (`openai/gpt-oss-120b` / `qwen/qwen3.8-27b`)** (com fallback opcional para **Ollama local `qwen2.5:7b`** e síntese extrativa determinística) e respeitando rigorosamente os limites da **Lei Federal nº 8.234/1991 (Art. 3º - CFN)**.

---

## Resumo dos Artefatos da Entrega

Detalhes, números gerados pelo sistema, diagramas e limitações em [`docs/entrega-rag-nutricao.md`](docs/entrega-rag-nutricao.md).

1. **Base de conhecimento curada:** 22 documentos-fonte em PDF (mínimo exigido: 20), catalogados em [`corpus/manifest.yaml`](corpus/manifest.yaml) com origem, licença e SHA-256, divididos em 1.873 Trechos. O `seed_guidelines` (sem origem verificável) e os resumos do PubMed (em inglês) ficaram fora do índice.
2. **Chunking:** `corpus/scripts/prepare_rag.py` gera Trechos de cerca de 1.000 caracteres sem atravessar página nem seção, no formato do [ADR 0002](docs/adrs/0002-contrato-corpus-retriever.md), com cabeçalho contextual na indexação.
3. **Embeddings:** `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (384 dimensões, cosseno), executado localmente, combinado ao BM25 por RRF.
4. **Banco vetorial:** ChromaDB persistente em `data/vector_store/chroma_db`, índice HNSW por cosseno, coleção versionada pela impressão digital do conteúdo e metadados de rastreabilidade (fonte, página, link, licença, aprovação).
5. **Gate de aprovação:** por padrão só fontes `aprovado` entram no índice. A demonstração e o benchmark usam a flag de desenvolvimento, que inclui as pendentes (`CULTIVA_INCLUIR_PENDENTES=true` na API e na CLI).

---

## Como Executar

### 1. Instalar dependências e verificar integridade do Corpus Oficial
```bash
uv sync
uv run python corpus/scripts/verify_corpus.py
```

### 2. Executar a Demonstração Oficial da Entrega (Artefatos + Consulta + Chunks + Resposta + Fontes)
```bash
# Executa a auditoria dos artefatos (>= 20 fontes, chunking, embeddings, ChromaDB) e 3 consultas completas:
uv run python -m src.demo_entrega

# Ou submeta uma pergunta específica na demonstração:
uv run python -m src.demo_entrega "Como a fibra solúvel da aveia age para reduzir o colesterol LDL e a glicemia?"
```

### 3. Rodar a suíte de testes automatizados
```bash
uv run pytest -v
```

### 4. Executar o Benchmark (16 questões) e Estudo de Ablação
```bash
# Estudo de Ablação rápido (Passo 1 vs. Passo 2 vs. Passo 3):
uv run python -m src.evaluation.run_benchmark --no-ollama --ablation

# Benchmark completo com LLM (Groq / Ollama):
uv run python -m src.evaluation.run_benchmark
```

### 5. Fazer uma consulta via CLI ou API FastAPI
```bash
# Consulta via CLI (exibe Chunks Recuperados, Síntese, Grafo, TACO e Citações):
uv run python -m src.api "Como a fibra solúvel da aveia age para reduzir o colesterol LDL e a glicemia?"

# Subir servidor FastAPI (Swagger em http://localhost:8000/docs):
uv run uvicorn src.api:app --reload
```
