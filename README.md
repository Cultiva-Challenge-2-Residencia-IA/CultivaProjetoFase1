# CultivaProjetoFase1 — Módulo de Nutrição Baseada em Evidências (`rag-hibrido`)

Projeto: CULTIVA, um aplicativo que usa IA para ajudar jovens adultos e estudantes a transformar bons hábitos em decisões simples e sustentáveis, sem substituir o profissional. Alinhado aos ODS 3 (Saúde e Bem-Estar) e 4 (Educação de Qualidade).

---

## Consultor Científico de Nutrição Baseado em Evidências (RAG Híbrido + TACO + Grafo Causal)

Implementação completa em 3 passos de um consultor de nutrição baseado em evidências científicas e diretrizes oficiais, operando com a **API gratuita da Groq (`openai/gpt-oss-120b` / `qwen/qwen3.8-27b`)** (com fallback opcional para **Ollama local `qwen2.5:7b`**) e respeitando rigorosamente os limites da **Lei Federal nº 8.234/1991 (Art. 3º - CFN)**.

## Arquitetura em 3 Passos

1. **Passo 1 — Contextual Chunking & RAG Híbrido (`src/ingestion/` & `src/retrieval/hybrid_retriever.py`):**
   * **Contextual Chunking:** Divide o *Guia Alimentar para a População Brasileira (2ª Ed. Oficial)*, *34 Meta-Análises/Revisões Sistemáticas do PubMed* e *Diretrizes Clínicas (SBD, SBC, ISSN, COI)* preservando a hierarquia de seções e o grau de evidência (`GRADE_A`, `GRADE_B`, `GUIDELINE_CONSENSUS`).
   * **Fusão RRF (`BM25` + `Vetorial SVD Local`) + Reranker Clínico:** Combina busca léxica biomédica e busca semântica densa com diversificação documental.
2. **Passo 2 — Ferramenta Determinística da Tabela TACO (`src/retrieval/taco_tool.py`):**
   * Consulta exata e ranking matemático por 100g sobre os **597 alimentos brasileiros** da *Tabela TACO 4ª Edição (Unicamp) / TBCA-USP*.
3. **Passo 3 — Grafo de Conhecimento Causal de 4 Camadas (`src/retrieval/graph_engine.py`):**
   * Grafo `NetworkX` (`MultiDiGraph`) estruturado em 4 camadas (`Alimento ➔ Composto Bioativo ➔ Mecanismo Fisiológico ➔ Desfecho Clínico PICO/GRADE`), validando sinergias de biodisponibilidade (ex.: *Curcumina + Piperina*) e filtrando contraindicações em comorbidades múltiplas (ex.: risco de hipercalemia do potássio na Doença Renal Crônica).
4. **Guardrails Ético-Legais (`src/agent/guardrails.py`):**
   * **Input Guardrail & Reframing:** Bloqueia pedidos de prescrição de cardápio/dieta individualizada, diagnóstico clínico por exames ou posologia personalizada de suplementos (Lei nº 8.234/91) e reenquadra para consulta PICO populacional.
   * **Output Guardrail:** Remove expressões imperativas/prescritivas individuais na saída.
5. **Síntese Estruturada via Groq API (`src/agent/llm_client.py`):**
   * Integra-se à API gratuita da **Groq (`openai/gpt-oss-120b` / `qwen/qwen3.8-27b`)**, com fallback para **Ollama local** e síntese extrativa determinística.

## Como Executar

### 1. Configurar variáveis de ambiente (`.env`)
```bash
cp .env.example .env
# Edite o arquivo .env e adicione sua chave gratuita da Groq (https://console.groq.com/keys):
# GROQ_API_KEY=gsk_...
```

### 2. Rodar a suíte de testes automatizados (21 testes)
```bash
uv run pytest -v
```

### 3. Executar o Benchmark (16 questões) e Estudo de Ablação
```bash
# Estudo de Ablação rápido (Passo 1 vs. Passo 2 vs. Passo 3):
uv run python -m src.evaluation.run_benchmark --no-ollama --ablation

# Benchmark completo com LLM (Groq / Ollama):
uv run python -m src.evaluation.run_benchmark
```

### 3. Fazer uma consulta via CLI ou API FastAPI
```bash
# Consulta via CLI:
uv run python -m src.api "Como a fibra solúvel da aveia age para reduzir o colesterol LDL e a glicemia?"

# Subir servidor FastAPI (Swagger em http://localhost:8000/docs):
uv run uvicorn src.api:app --reload
```
