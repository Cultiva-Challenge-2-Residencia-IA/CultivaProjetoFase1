# CultivaProjetoFase1 — Módulo de Nutrição Baseada em Evidências (`rag-hibrido`)

Projeto: CULTIVA, um aplicativo que usa IA para ajudar jovens adultos e estudantes a transformar bons hábitos em decisões simples e sustentáveis, sem substituir o profissional. Alinhado aos ODS 3 (Saúde e Bem-Estar) e 4 (Educação de Qualidade).

---

## Consultor Científico de Nutrição Baseado em Evidências (RAG Híbrido + TACO + Grafo Causal)

Implementação completa em 3 passos de um consultor de nutrição baseado em evidências científicas e diretrizes oficiais, operando com modelo local (**Ollama `qwen2.5:7b` / `qwen2.5:3b`**) e respeitando rigorosamente os limites da **Lei Federal nº 8.234/1991 (Art. 3º - CFN)**.

## Arquitetura da Fase 1 (Baseline)

1. **Contextual Chunking (`src/ingestion/contextual_chunker.py`):**
   Divide as diretrizes e revisões sistemáticas preservando a hierarquia de seções e injetando o cabeçalho contextual (`[Documento | Fonte | Domínio | Nível GRADE | Seção]`) em cada chunk.
2. **Motor de RAG Híbrido (`src/retrieval/hybrid_retriever.py`):**
   * **Busca Léxica (BM25):** Tokenizador biomédico em português que preserva siglas (`HbA1c`, `LDL-c`, `mTORC1`, `EGCG`, `GLP-1`, `CYP1A2`, `Fe2+`).
   * **Busca Vetorial Densa Local:** Representação semântica local (TF-IDF n-gramas + SVD/LSA normalizado por cosseno) com expansão de sinônimos clínicos.
   * **Fusão RRF (`Reciprocal Rank Fusion`) + Reranker Clínico:** Combina os rankings léxico e vetorial e aplica bônus de cobertura conceitual e grau de evidência (`GRADE_A`, `GRADE_B`, `GUIDELINE_CONSENSUS`).
3. **Guardrails Legais (`src/agent/guardrails.py`):**
   * **Input Guardrail & Reframing:** Detecta pedidos de prescrição de cardápio/dieta individualizada, diagnóstico clínico por exames ou posologia personalizada de suplementos, exibe a nota de conformidade com a Lei nº 8.234/91 e reescreve a consulta para o formato PICO populacional.
   * **Output Guardrail:** Bloqueia expressões imperativas/prescritivas individuais na saída.
4. **Síntese Local (`src/agent/llm_client.py`):**
   Integra-se ao **Ollama local (`qwen2.5:7b` / `qwen2.5:3b`)** com saída JSON estruturada e possui síntese extrativa determinística integrada como fallback.

## Como Executar

### 1. Instalar dependências e rodar os testes automatizados
```bash
uv run pytest -v
```

### 2. Executar a Suíte de Benchmark do Baseline
```bash
# Usando síntese determinística rápida:
uv run python -m src.evaluation.run_benchmark --no-ollama

# Usando o modelo local no Ollama (qwen2.5:7b):
uv run python -m src.evaluation.run_benchmark
```

### 3. Fazer uma consulta via CLI ou API FastAPI
```bash
# Consulta via CLI:
uv run python -m src.api "Como a fibra solúvel da aveia age para reduzir o colesterol LDL e a glicemia?"

# Subir servidor FastAPI (Swagger em http://localhost:8000/docs):
uv run uvicorn src.api:app --reload
```
