# CultivaProjetoFase1 — Módulo de Nutrição Baseada em Evidências (`rag-hibrido`)

Projeto: CULTIVA, um aplicativo que usa IA para ajudar jovens adultos e estudantes a transformar bons hábitos em decisões simples e sustentáveis, sem substituir o profissional. Alinhado aos ODS 3 (Saúde e Bem-Estar) e 4 (Educação de Qualidade).

---

## Consultor Científico de Nutrição Baseado em Evidências (RAG Híbrido + TACO + Grafo Causal)

Protótipo técnico em 3 passos de um consultor de nutrição, com execução bloqueada até que as fontes sejam aprovadas para o uso pretendido. A síntese pode usar a **API da Groq** ou **Ollama local**; isso não comprova qualidade clínica nem aprovação institucional. O sistema não substitui profissionais.

## Arquitetura em 3 Passos

1. **Passo 1 — Contextual Chunking & RAG Híbrido (`src/ingestion/` & `src/retrieval/hybrid_retriever.py`):**
   * **Contextual Chunking:** O carregador aceita apenas conjuntos aprovados no [manifesto do corpus](corpus/manifest.yaml). Neste momento, indexa somente o Guia Alimentar do Ministério da Saúde (235 chunks), para uso não comercial sob CC-BY-NC-SA-4.0; PubMed e `seed_guidelines` permanecem fora do índice.
   * **Fusão RRF (`BM25` + `Vetorial SVD Local`) + Reranker Clínico:** Combina busca léxica biomédica e busca semântica densa com diversificação documental.
2. **Passo 2 — Ferramenta Determinística da Tabela TACO (`src/retrieval/taco_tool.py`):**
   * Ferramenta determinística preparada para consultar a *Tabela TACO 4ª Edição (Unicamp)* por 100 g; está desativada enquanto licença, revisão e aprovação não forem concluídas. Complementos TBCA são uma fonte distinta e também estão bloqueados.
3. **Passo 3 — Grafo de Conhecimento Causal de 4 Camadas (`src/retrieval/graph_engine.py`):**
   * O protótipo define um grafo `NetworkX` de 4 camadas, mas as 14 cadeias atuais estão marcadas como sem fonte citável e não são carregadas nas respostas.
4. **Guardrails Ético-Legais (`src/agent/guardrails.py`):**
   * **Input Guardrail & Reframing:** Bloqueia pedidos de prescrição de cardápio/dieta individualizada, diagnóstico clínico por exames ou posologia personalizada de suplementos (Lei nº 8.234/91) e reenquadra para consulta PICO populacional.
   * **Output Guardrail:** Remove expressões imperativas/prescritivas individuais na saída.
5. **Síntese Estruturada via Groq API (`src/agent/llm_client.py`):**
   * Integra-se à API gratuita da **Groq (`openai/gpt-oss-120b` / `qwen/qwen3.8-27b`)**, com fallback para **Ollama local** e síntese extrativa determinística.

## Procedência das fontes e limites de uso

O repositório separa claramente entre fonte documental, dado de composição e inferência causal. Essa distinção é importante porque a arquitetura atual é uma proposta em evolução e não equivale a aprovação clínica ou autorização institucional de uso.

| Fonte | Evidência no repositório | Classificação | Observação prática |
| --- | --- | --- | --- |
| Guia Alimentar do Ministério da Saúde | [data/raw/guidelines/guia_alimentar_ms_2ed.json](data/raw/guidelines/guia_alimentar_ms_2ed.json) | Aprovado para uso não comercial | Revisão manual informada pelo solicitante em 05/11/2026; licença CC-BY-NC-SA-4.0 identificada no PDF. Uso comercial não liberado. |
| `seed_guidelines.json` | [data/raw/guidelines/seed_guidelines.json](data/raw/guidelines/seed_guidelines.json) | Removido do índice | Os 10 documentos não têm URL/DOI individual nem licença rastreável; permanecem arquivados apenas para auditoria. |
| PubMed / NCBI Entrez | [src/ingestion/pubmed_ingestor.py](src/ingestion/pubmed_ingestor.py) e [data/raw/guidelines/pubmed_clinical_evidence.json](data/raw/guidelines/pubmed_clinical_evidence.json) | Citação identificável; licença por artigo pendente e registros removidos do índice | Os 31 artigos distintos têm PMID/DOI e URL PubMed. A NLM informa que autores ou editores podem deter direitos dos resumos; a coleta não libera sua reprodução. A data da coleta original também não está registrada no JSON. |
| TACO | [data/raw/taco/taco_raw.json](data/raw/taco/taco_raw.json) | Citação registrada; licença pendente; removido do índice | Referência bibliográfica registrada no manifesto. Os termos de reutilização do conjunto local não foram confirmados. |
| TBCA-USP | [src/retrieval/taco_tool.py](src/retrieval/taco_tool.py) e [TBCA](https://www.tbca.net.br/) | Termos registrados; dados complementares removidos do índice | O portal estimula divulgação sem fins comerciais com citação, proíbe reprodução total/parcial e orienta contato dos coordenadores para uso comercial. Valores locais embutidos não têm referência individual. |
| Grafo causal de 4 camadas | [data/raw/knowledge_graph/nutrition_4layer_graph.json](data/raw/knowledge_graph/nutrition_4layer_graph.json) | 14 cadeias marcadas `sem_fonte`; fora das respostas | `source_reference` contém nomes genéricos, não URLs ou DOIs. As cadeias ficam preservadas para revisão, não como evidência clínica. |

No estado registrado em [corpus/manifest.yaml](corpus/manifest.yaml), o índice contém apenas o Guia Alimentar aprovado. O uso está limitado a contexto não comercial; antes de operação comercial, é necessário avaliar a licença e obter autorização compatível. Não usar os outros conjuntos bloqueados para fundamentar respostas.

### Boas práticas adotadas

* Manter a origem explícita em cada documento ou registro (`source_organization`, `publication_year`, `source_reference`, `PMID`, `DOI` quando disponível).
* Separar “evidência recuperada” de “inferencia causal local” no fluxo de resposta; o grafo e a síntese final não devem ser apresentados como se fossem uma diretiva oficial.
* Registrar data de coleta e versionamento da base de dados externa, especialmente no caso de PubMed, TACO e dados complementares.
* Tratar valores numéricos da TACO como referência de composição e não como substituto de revisão clínica.

> Em outras palavras: a arquitetura funciona como um pipeline de suporte analítico, porém a aprovação de fontes e o uso clínico final seguem pendentes e devem ser confirmados por revisão humana, revisão documental e avaliação legal antes de qualquer uso de produção.

## Como Executar

O carregador inicializa com o Guia Alimentar aprovado. Benchmark e consultas não devem tratar PubMed, TACO/TBCA ou grafo como evidência disponível enquanto seus registros permanecerem bloqueados no manifesto.

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
