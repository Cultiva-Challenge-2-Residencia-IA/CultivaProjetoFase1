# Documentação Técnica Completa — Consultor Científico de Nutrição Baseado em Evidências (`CultivaProjetoFase1` / `rag-hibrido`)

Este documento descreve em profundidade toda a engenharia, arquitetura matemática, bases de conhecimento, estrutura de arquivos, fluxo de processamento de perguntas e resultados experimentais do módulo de **Nutrição Baseada em Evidências** do projeto **CULTIVA**.

---

## Sumário

1. [Visão Geral, Escopo e Conformidade Ético-Legal (Lei nº 8.234/1991)](#1-visão-geral-escopo-e-conformidade-ético-legal-lei-nº-82341991)
2. [Estrutura Completa de Diretórios e Função de Cada Arquivo](#2-estrutura-completa-de-diretórios-e-função-de-cada-arquivo)
3. [Bases de Conhecimento e Pipeline de Ingestão](#3-bases-de-conhecimento-e-pipeline-de-ingestão)
4. [Engenharia Detalhada do Passo 1: Contextual Chunking e RAG Híbrido](#4-engenharia-detalhada-do-passo-1-contextual-chunking-e-rag-híbrido)
5. [Engenharia Detalhada do Passo 2: Ferramenta Determinística da Tabela TACO](#5-engenharia-detalhada-do-passo-2-ferramenta-determinística-da-tabela-taco)
6. [Engenharia Detalhada do Passo 3: Grafo de Conhecimento Causal de 4 Camadas (`NetworkX`)](#6-engenharia-detalhada-do-passo-3-grafo-de-conhecimento-causal-de-4-camadas-networkx)
7. [Camada de Guardrails Ético-Legais e Clínicos](#7-camada-de-guardrails-ético-legais-e-clínicos)
8. [Fluxo Completo de Processamento de uma Pergunta (As 6 Etapas)](#8-fluxo-completo-de-processamento-de-uma-pergunta-as-6-etapas)
9. [Rastreamento Prático Ponta a Ponta de uma Pergunta Real](#9-rastreamento-prático-ponta-a-ponta-de-uma-pergunta-real)
10. [Suíte de Benchmark (16 Questões), Estudo de Ablação e Resultados](#10-suíte-de-benchmark-16-questões-estudo-de-ablação-e-resultados)
11. [Guia de Execução e Comandos Rápidos](#11-guia-de-execução-e-comandos-rápidos)

---

## 1. Visão Geral, Escopo e Conformidade Ético-Legal (Lei nº 8.234/1991)

O **Consultor Científico de Nutrição Baseado em Evidências** foi projetado para responder dúvidas gerais e cotidianas sobre alimentação, nutrição clínica, composição de alimentos brasileiros e sinergias culinárias fundamentando-se estritamente em diretrizes oficiais e literatura científica revisada por pares (**PICO / GRADE**).

### 1.1. Limite Legal Inegociável (Lei Federal nº 8.234/1991 — CFN)
No Brasil, o **Art. 3º, inciso VIII da Lei Federal nº 8.234/1991** determina que a **prescrição dietética** é atividade privativa do nutricionista habilitado. Portanto, este sistema:
* **NUNCA** prescreve cardápios personalizados, dietas com cálculo calórico individual (`kcal`), quantidades em gramas por refeição para um indivíduo específico, diagnósticos clínicos por exames laboratoriais ou posologia individualizada de suplementos.
* **SEMPRE** atua como ferramenta de educação em saúde e consulta científica populacional: quando recebe um pedido restrito pela lei, aciona um **Guardrail de Entrada**, exibe a nota oficial de conformidade do Conselho Federal de Nutricionistas (CFN) e **reenquadra a pergunta para o formato PICO populacional**, explicando o que as diretrizes clínicas demonstram sobre o tema sem realizar prescrição individual.

### 1.2. Arquitetura Neuro-Simbólica em 3 Passos
Para superar as três principais falhas de sistemas baseados apenas em LLMs ou RAG simples (alucinação de números nutricionais, incapacidade de conectar múltiplos saltos bioquímicos e cegueira a contraindicações médicas cruzadas), o sistema combina três motores determinísticos antes da geração textual pela **API gratuita da Groq (`openai/gpt-oss-120b` / `qwen/qwen3.8-27b`)**:

1. **Passo 1 — RAG Híbrido Multi-Documento (`BM25 + Vetorial SVD + Fusão RRF + Reranker GRADE`):** Recupera trechos exatos do *Guia Alimentar para a População Brasileira (MS)*, de *34 Meta-Análises do PubMed* e de *Diretrizes da SBD, SBC, ISSN e COI*.
2. **Passo 2 — Ferramenta Determinística da Tabela TACO (`TacoDeterministicTool`):** Consulta e ordena matematicamente os valores exatos por `100g` dos **597 alimentos brasileiros** da *Tabela TACO 4ª Edição (NEPA/Unicamp) & TBCA-USP*.
3. **Passo 3 — Grafo de Conhecimento Causal de 4 Camadas (`CausalKnowledgeGraphEngine` em `NetworkX`):** Percorre cadeias estruturadas (`Alimento ➔ Composto Bioativo ➔ Mecanismo Fisiológico ➔ Desfecho Clínico GRADE`), diferenciando compostos isolados de sinergias culinárias e filtrando contraindicações em comorbidades múltiplas (como restrição de potássio na Doença Renal Crônica).

---

## 2. Estrutura Completa de Diretórios e Função de Cada Arquivo

```text
projeto_2/
├── pyproject.toml                  # Dependências gerenciadas via uv e configuração do pytest
├── uv.lock                         # Lockfile determinístico das bibliotecas Python
├── .env.example                    # Modelo de configuração (Groq API, Ollama e hiperparâmetros RAG)
├── .gitignore                      # Protege .env, .venv e caches de serem enviados ao Git
├── README.md                       # Guia rápido de instalação e uso
├── CONTEXTO_PROJETO.md             # Resumo executivo de transferência de contexto
├── DOCUMENTACAO_COMPLETA_PROJETO.md # Este documento técnico detalhado
│
├── corpus/                         # Registro oficial do Corpus (Padrão CULTIVA)
│   ├── manifest.yaml               # Declaração de versão, origem, licença e nível GRADE das 5 fontes
│   └── scripts/
│       ├── ingest_pdf_guia_alimentar.py # Ponto de entrada para extração do PDF do Guia Alimentar MS
│       └── ingest_pubmed_evidence.py    # Ponto de entrada para coleta na API Entrez do PubMed/NCBI
│
├── data/                           # Armazenamento das bases de dados brutas, processadas e benchmark
│   ├── raw/
│   │   ├── pdfs/
│   │   │   └── guia_alimentar_populacao_brasileira_2ed.pdf # PDF oficial de 158 páginas (4.2 MB)
│   │   ├── guidelines/
│   │   │   ├── guia_alimentar_ms_2ed.json       # 8 capítulos + 10 passos extraídos do PDF (120 seções)
│   │   │   ├── pubmed_clinical_evidence.json    # 34 Meta-Análises e Revisões Sistemáticas reais (PMID/DOI)
│   │   │   └── seed_guidelines.json             # 10 diretrizes clínicas em português (SBD, SBC, ISSN, COI)
│   │   ├── taco/
│   │   │   └── taco_raw.json                    # 597 alimentos oficiais da Tabela TACO 4ª Edição (Unicamp)
│   │   └── knowledge_graph/
│   │       └── nutrition_4layer_graph.json      # 14 rotas causais completas de 4 camadas (FooDB/PubMed/GRADE)
│   └── benchmark/
│       ├── eval_questions.json                  # 16 perguntas de avaliação (diretas, multi-hop, cotidianas e traps legais)
│       └── baseline_report.json                 # Relatório JSON com métricas por pergunta e estudo de ablação
│
├── src/                            # Código-fonte principal da aplicação
│   ├── __init__.py
│   ├── config.py                   # Carregamento de variáveis de ambiente e constantes de arquitetura
│   ├── api.py                      # Servidor FastAPI (GET /health, POST /consult) e interface de linha de comando (CLI)
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   └── schemas.py              # Contratos de dados Pydantic (DocumentChunk, CausalGraphPath, ConsultantResponse, etc.)
│   │
│   ├── ingestion/
│   │   ├── __init__.py
│   │   ├── pdf_ingestor.py         # Extrator paginado do PDF do Guia Alimentar MS via pypdf
│   │   ├── pubmed_ingestor.py      # Coletor XML/JSON da API NCBI Entrez (esearch + efetch)
│   │   └── contextual_chunker.py   # Fatiador semântico que injeta cabeçalhos contextuais nos 342 chunks
│   │
│   ├── retrieval/
│   │   ├── __init__.py
│   │   ├── hybrid_retriever.py     # Motor do Passo 1: Sinônimos Clínicos + BM25 + TF-IDF/SVD + Fusão RRF + Reranker
│   │   ├── taco_tool.py            # Motor do Passo 2: Busca exata e ranking matemático na Tabela TACO (597 alimentos)
│   │   └── graph_engine.py         # Motor do Passo 3: Grafo NetworkX de 4 camadas, sinergia e contraindicações
│   │
│   ├── rag/                        # Pacote modular RAG alinhado à estrutura da branch main (CULTIVA)
│   │   ├── __init__.py
│   │   ├── chunking/__init__.py    # Expõe ContextualChunker
│   │   ├── retriever/__init__.py   # Expõe HybridRetriever e TacoDeterministicTool
│   │   ├── reranker/
│   │   │   ├── __init__.py
│   │   │   └── clinical_reranker.py # Classe ClinicalEvidenceReranker (bônus GRADE e diversificação)
│   │   └── verificador/
│   │       ├── __init__.py
│   │       └── graph_verifier.py    # Classe GraphClinicalVerifier (auditoria de alertas do grafo)
│   │
│   ├── guardrails/                 # Pacote modular de Guardrails alinhado à branch main (CULTIVA)
│   │   ├── __init__.py
│   │   ├── prescricao/__init__.py  # Regras de bloqueio e reenquadramento PICO da Lei Federal nº 8.234/91
│   │   ├── risco/__init__.py       # Detector de flags de risco clínico (restrição renal de potássio, anticoagulantes)
│   │   ├── tom/__init__.py         # Sanitizador de linguagem imperativa/prescritiva na saída
│   │   └── injection/__init__.py   # Detector de tentativas de Prompt Injection / Jailbreak
│   │
│   ├── agent/                      # Implementação central do Agente Consultor e Cliente LLM
│   │   ├── __init__.py
│   │   ├── guardrails.py           # Classe LegalGuardrail (assess_and_reframe e sanitize_output_text)
│   │   ├── llm_client.py           # Classe LocalLLMClient (Groq API -> Ollama Local -> Fallback Extrativo)
│   │   └── consultant_baseline.py  # Classe orquestradora NutritionConsultantBaseline
│   │
│   ├── agents/                     # Pacote de Agentes Especialistas (Padrão CULTIVA)
│   │   ├── __init__.py
│   │   └── nutricao/__init__.py    # Expõe NutritionConsultantBaseline e LocalLLMClient
│   │
│   └── evaluation/
│       ├── __init__.py
│       └── run_benchmark.py        # Executor do Benchmark de 16 questões e do Estudo de Ablação
│
├── eval/                           # Espelho oficial de avaliação (Padrão CULTIVA)
│   ├── golden/
│   │   ├── dev/nutricao_eval_questions.json
│   │   └── test/nutricao_holdout_questions.json
│   └── runs/
│       └── latest_ablation_report.json
│
├── docs/                           # Documentação de Governança e Decisões Arquiteturais
│   ├── adrs/0001-arquitetura-rag-hibrido-taco-grafo-4-camadas.md
│   ├── ripd/ripd-conformidade-lgpd-e-lei-8234-cfn.md
│   └── rubric/rubrica-avaliacao-nutricao-evidencias.md
│
├── specs/
│   └── nutricao_4layer_schema_spec.md # Especificação formal da ontologia de 4 camadas e contratos REST
├── notebooks/eda/
│   └── eda_corpus_taco_e_grafo.py     # Script de Análise Exploratória das bases (342 chunks, TACO, Grafo)
├── infra/
│   └── Dockerfile                     # Imagem Docker para execução do servidor FastAPI
└── tests/                          # Suíte com 22 testes automatizados (pytest)
    ├── test_guardrails.py          # 5 testes da Lei 8.234/91 e sanitização de saída
    ├── test_hybrid_retriever.py    # 4 testes de chunking contextual, BM25+SVD e diversificação
    ├── test_taco_tool.py           # 4 testes de precisão numérica nos 597 alimentos da TACO
    ├── test_graph_engine.py        # 4 testes de travessia de 4 camadas, sinergia e contraindicação renal
    └── test_consultant_baseline.py # 5 testes ponta a ponta (incluindo integração Groq e pacotes Cultiva)
```

---

## 3. Bases de Conhecimento e Pipeline de Ingestão

O sistema não utiliza textos fictícios: toda a recuperação é feita sobre **5 fontes reais e auditáveis** declaradas em `corpus/manifest.yaml`:

| Fonte de Conhecimento | Arquivo Local | Volume de Dados | Papel na Arquitetura |
| :--- | :--- | :--- | :--- |
| **1. Guia Alimentar para a População Brasileira (2ª Edição Oficial)** | `data/raw/guidelines/guia_alimentar_ms_2ed.json` | 8 documentos (120 seções paginadas extraídas das 158 páginas do PDF oficial do Ministério da Saúde) | Orientações normativas oficiais sobre Classificação NOVA, Regra de Ouro, comensalidade, refeições brasileiras e obstáculos alimentares (`GUIDELINE_CONSENSUS`). |
| **2. Meta-Análises e Revisões Sistemáticas do PubMed / NCBI** | `data/raw/guidelines/pubmed_clinical_evidence.json` | 34 estudos revisados por pares indexados com `PMID` e `DOI` reais | Evidência clínica quantitativa internacional em humanos sobre controle glicêmico, dieta DASH, dislipidemia, fitoquímicos e suplementação (`GRADE_A` / `GRADE_B`). |
| **3. Diretrizes Clínicas SBD, SBC, ISSN e COI (`seed_guidelines.json`)** | `data/raw/guidelines/seed_guidelines.json` | 10 diretrizes temáticas (17 seções técnicas detalhadas em português) | Sínteses mecanicistas em português cobrindo fibras/microbiota (`AGCC`, `GLP-1`), diabetes (`HOMA-IR`, `RS3`), colesterol (`LDLR`, fitoesteróis), hipertensão (`DASH`, nitratos), proteínas (`mTORC1`, leucina), suplementos (`creatina`, `cafeína`), biodisponibilidade (`curcumina+piperina`, `sulforafano`) e ferro (`Vitamina C` vs. `taninos/fitatos`). |
| **4. Tabela TACO 4ª Edição (NEPA/Unicamp) + TBCA-USP** | `data/raw/taco/taco_raw.json` | **597 alimentos brasileiros** com composição centesimal completa por `100g` | Fonte determinística exata para energia (`kcal`), proteínas, carboidratos, lipídeos, fibras, cálcio, magnésio, ferro, sódio, potássio, zinco, vitamina C e selênio. |
| **5. Grafo Causal de 4 Camadas (`FooDB` + `TACO` + `PubMed/GRADE`)** | `data/raw/knowledge_graph/nutrition_4layer_graph.json` | **14 cadeias causais completas** (**56 nós e 42 arestas** no `NetworkX`) | Conecta `Alimento ➔ Composto Bioativo ➔ Mecanismo Fisiológico ➔ Desfecho Clínico GRADE`, incluindo alertas de baixa eficácia isolada e contraindicações médicas. |

---

## 4. Engenharia Detalhada do Passo 1: Contextual Chunking e RAG Híbrido

O Passo 1 é responsável por transformar os documentos científicos em fragmentos autocontidos e recuperar os trechos mais relevantes combinando **precisão léxica** e **compreensão semântica**.

### 4.1. Contextual Chunking (`src/ingestion/contextual_chunker.py`)
Em um sistema RAG comum, quando um documento longo é dividido em pedaços menores, frases como *"A ingestão de 3g ao dia reduz os níveis séricos em 10%"* perdem a referência de qual composto, qual doença e qual diretriz estão sendo discutidos.

A classe `ContextualChunker` resolve isso em 3 passos:
1. Lê todos os arquivos `.json` de `data/raw/guidelines/` validando-os com `GuidelineDocumentInput`.
2. Divide textos longos respeitando estritamente o limite de sentenças (`.` final) até o teto de `1200 caracteres` (`_split_long_text`).
3. **Injeção de Cabeçalho Contextual (`build_context_header`):** Antes de indexar o texto, prefixa cada um dos **342 chunks** gerados com sua árvore completa de metadados:
   ```text
   [Documento: Diretriz da Sociedade Brasileira de Diabetes | Fonte: Sociedade Brasileira de Diabetes (SBD) (2024) | Domínio: Controle Glicêmico, Resistência à Insulina e Diabetes Tipo 2 | Nível de Evidência: GRADE_A | Seção: Estratégias Glicêmicas > Carga Glicêmica, Ordem da Refeição e Amido Resistente]
   Texto integral do fragmento...
   ```

### 4.2. Expansão Bilíngue de Sinônimos Clínicos e Tokenização Biomédica (`src/retrieval/hybrid_retriever.py`)
Usuários fazem perguntas usando termos populares em português (*"açúcar no sangue"*, *"pressão alta"*, *"colesterol ruim"*, *"açafrão"*, *"dormir pouco"*), enquanto os artigos do PubMed e diretrizes utilizam termos técnicos em português e inglês (`HbA1c`, `insulin resistance`, `LDL cholesterol`, `phytosterols`, `curcumin`, `piperine`, `glicuronidação`).

1. **`expand_clinical_synonyms(text)`:** Consulta o dicionário `CLINICAL_SYNONYMS` (33 mapeamentos clínicos) e anexa automaticamente os termos técnicos em português e inglês à consulta.
2. **`tokenize_biomedical(text)`:** Diferente de tokenizadores comuns que destroem símbolos e números, a expressão regular `r"[a-z0-9]+(?:-[a-z0-9]+)*"` preserva intactas siglas bioquímicas essenciais como `hba1c`, `ldl-c`, `glp-1`, `mtorc1`, `cyp1a2`, `fe2+` e `homa-ir`, removendo apenas *stopwords* irrelevantes.

### 4.3. Índice Léxico (`BM25Okapi`) + Índice Vetorial Denso Local (`TF-IDF + TruncatedSVD`)
Na inicialização do `HybridRetriever`, dois índices matemáticos independentes são construídos em memória RAM sobre os 342 chunks:

1. **Índice Léxico (`BM25Okapi`):**
   * Pontua a correspondência exata de termos raros, siglas de enzimas, nomes de capítulos e números `PMID`.
   * Retorna os `TOP_K_BM25 = 8` chunks com maior pontuação léxica.
2. **Índice Vetorial Denso Local (`TF-IDF n-gramas + TruncatedSVD / LSA`):**
   * Extrai unigramas e bigramas (`ngram_range=(1, 2)`) com escala logarítmica (`sublinear_tf=True`).
   * Aplica **Decomposição em Valores Singulares Truncada (`TruncatedSVD`)** gerando uma matriz densa de conceitos latentes (`self.doc_vectors`) normalizada na esfera unitária ($L_2$), combinada à matriz esparsa normalizada (`self.tfidf_matrix_norm`).
   * Durante a consulta (`_search_vector`), calcula a similaridade de cosseno combinada:
     $$\text{Score}_{\text{vec}}(q, d) = 0.65 \cdot \cos(\text{TFIDF}_q, \text{TFIDF}_d) + 0.35 \cdot \cos(\text{SVD}_q, \text{SVD}_d)$$
   * Retorna os `TOP_K_VECTOR = 8` chunks mais próximos semanticamente.

### 4.4. Fusão por Reciprocal Rank Fusion (`RRF`), Reranker Clínico e Diversificação
Como a pontuação do `BM25` (escala aberta: `0` a `30+`) e a similaridade de cosseno (`0.0` a `1.0`) possuem distribuições incompatíveis, o sistema aplica **Reciprocal Rank Fusion (RRF)** sobre a posição ($r$) de cada chunk nos dois rankings (`RRF_K = 60`, `WEIGHT_BM25 = 0.55`, `WEIGHT_VECTOR = 0.45`):

$$\text{Score}_{\text{RRF}}(d) = \frac{0.55}{60 + r_{\text{BM25}}(d)} + \frac{0.45}{60 + r_{\text{Vetorial}}(d)}$$

Em seguida, aplica o **Reranker Clínico** e a **Diversificação Documental**:
1. **Bônus de Cobertura de Entidades:** Soma $+0.20 \times \frac{|Q \cap D|}{|Q|}$ para premiar chunks que concentram múltiplos conceitos da pergunta no mesmo parágrafo.
2. **Bônus de Evidência Científica (`EVIDENCE_GRADE_BONUS`):**
   * `GRADE_A`: `+0.08`
   * `GUIDELINE_CONSENSUS`: `+0.06`
   * `GRADE_B`: `+0.05`
   * `GRADE_C`: `+0.02`
3. **Filtro de Diversificação (`MAX_CHUNKS_PER_DOC = 2`):** Garante que os `TOP_K_FINAL = 4` chunks selecionados nunca sejam dominados por um único documento, trazendo múltiplas perspectivas (ex.: *Guia Alimentar MS* + *Diretriz SBD* + *Meta-Análise PubMed*).

---

## 5. Engenharia Detalhada do Passo 2: Ferramenta Determinística da Tabela TACO

Modelos de linguagem são probabilísticos e frequentemente inventam números quando questionados sobre quantos miligramas de um mineral existem em 100g de um alimento. O módulo [`src/retrieval/taco_tool.py`](file:///Users/aluno2/Documents/Residencia/projeto_2/src/retrieval/taco_tool.py) (`TacoDeterministicTool`) resolve esse problema por **computação determinística**.

### 5.1. Base de Dados e Enriquecimento (`taco_raw.json`)
* Carrega na memória os **597 alimentos brasileiros** da *Tabela TACO 4ª Edição (NEPA/Unicamp)*, complementados com valores de referência da **TBCA-USP** para selênio (`selenium_mcg`) em oleaginosas, sementes e leguminosas e para a semente de abóbora crua (`592.0 mg` de magnésio e `809.0 mg` de potássio por 100g).

### 5.2. Detecção Automática de Intenção Bromatológica (`auto_query_from_question`)
Sempre que uma pergunta é feita, a ferramenta analisa dois eixos:
1. **Gatilhos de Nutrientes (`NUTRIENT_TRIGGERS`):** Detecta menções a `magnésio`, `selênio`, `potássio`, `ferro`, `cálcio`, `sódio`, `zinco`, `vitamina c`, `fibra`, `proteína`, `lipídeos`, `carboidrato` e `calorias/energia`.
2. **Gatilhos de Alimentos (`FOOD_QUERY_TRIGGERS`):** Detecta menções a alimentos ou grupos alimentares (`castanha`, `nozes`, `semente`, `feijão`, `arroz`, `aveia`, `brócolis`, `couve`, `banana`, `abacate`, `ovo`, `salmão`, `sardinha`, `linhaça`, `gergelim`, `chia`, `grão-de-bico`, `lentilha`).

### 5.3.três Modos de Operação da Ferramenta TACO
* **Modo 1 (Alimento Específico + Nutriente Específico):** Se o usuário pergunta *"qual a quantidade de magnésio e selênio nas castanhas e feijões?"*, a ferramenta busca os alimentos correspondentes (`search_foods`), filtra ruídos industriais e ordena exatamente pelos nutrientes solicitados:
  * *Castanha-do-Brasil, crua:* `Magnésio: 365.12 mg | Selênio: 1917.0 mcg`
  * *Gergelim, semente:* `Magnésio: 360.69 mg | Selênio: 34.4 mcg`
  * *Linhaça, semente:* `Magnésio: 347.25 mg | Selênio: 25.4 mcg`
* **Modo 2 (Ranking Puro por Nutriente — `rank_foods_by_nutrient`):** Se o usuário pergunta *"quais alimentos têm mais magnésio?"*, a ferramenta vasculha os 597 alimentos e retorna o Top 5 matemático por `100g` (*Semente de abóbora: 592.0 mg*, *Coentro desidratado: 392.79 mg*, *Castanha-do-Brasil: 365.12 mg*, etc.).
* **Modo 3 (Consulta Silenciosa):** Se a pergunta for puramente conceitual (ex.: *"o que é comensalidade?"* ou *"tomar açafrão funciona?"*), retorna vazio (`[]`, `""`) para não poluir o prompt.

---

## 6. Engenharia Detalhada do Passo 3: Grafo de Conhecimento Causal de 4 Camadas (`NetworkX`)

O módulo [`src/retrieval/graph_engine.py`](file:///Users/aluno2/Documents/Residencia/projeto_2/src/retrieval/graph_engine.py) (`CausalKnowledgeGraphEngine`) resolve o problema de **raciocínio multi-hop (múltiplos saltos)**, **sinergia de biodisponibilidade** e **contraindicações clínicas cruzadas**.

### 6.1. Por que um Grafo Controlado de 4 Camadas (e não um GraphRAG aberto)?
Quando um LLM extrai livremente nós e arestas de textos médicos (*GraphRAG não-supervisionado*), ele frequentemente cria conexões falsas ou ignora restrições vitais de segurança. Por isso, implementamos um **Grafo Causal Controlado** em `networkx.MultiDiGraph` validado pelo schema Pydantic `CausalGraphPath`:

```mermaid
flowchart LR
    F["Camada 1: FOOD<br/>(Alimento / Preparo Culinário)"] -->|CONTAINS<br/>key = path_id| C["Camada 2: COMPOUND<br/>(Composto Bioativo + Concentração)"]
    C -->|TRIGGERS_MECHANISM<br/>key = path_id| M["Camada 3: MECHANISM<br/>(Via Enzimática / Fisiológica)"]
    M -->|CAUSES_EFFECT<br/>key = path_id + GRADE + Contraindicações| O["Camada 4: OUTCOME<br/>(Desfecho Clínico PICO)"]
```

### 6.2. As 14 Rotas Causais Cadastradas em `nutrition_4layer_graph.json`
O grafo possui **56 nós e 42 arestas** distribuídos em **14 rotas causais completas (`KG_PATH_01` a `KG_PATH_14`)**:
1. **`KG_PATH_01_AVEIA_BETAGLUCANA`:** Aveia/Psyllium/Leguminosas $\rightarrow$ Fibras Solúveis Viscosas ($\beta$-glucana) $\rightarrow$ Viscosidade luminal e retardo de $\alpha$-amilase $\rightarrow$ Redução de glicemia pós-prandial, `HbA1c` e `HOMA-IR` (`GRADE_A`).
2. **`KG_PATH_02_AMIDO_RESISTENTE_RESFRIAMENTO`:** Arroz/Batata/Mandioca/Feijão cozidos e resfriados (12–24h a 4°C) $\rightarrow$ Amido Resistente Tipo 3 (`RS3`) $\rightarrow$ Retrogradação da amilose + fermentação colônica gerando `AGCC` (butirato/propionato) e `GLP-1`/`PYY` $\rightarrow$ Redução de `HOMA-IR`, pico glicêmico e pressão arterial sem elevar potássio (`GRADE_A`).
3. **`KG_PATH_03_ARROZ_FEIJAO_AMINOACIDOS`:** Combinação de Feijão com Arroz $\rightarrow$ Lisina (feijão) + Metionina (arroz) $\rightarrow$ Complementaridade de aminoácidos essenciais (`PDCAAS`) $\rightarrow$ Síntese proteica e saciedade (`GUIDELINE_CONSENSUS`).
4. **`KG_PATH_04_DASH_POTASSIO_HIPERTENSAO`:** Frutas/Hortaliças/Feijões/Sementes em alta quantidade (Padrão DASH) $\rightarrow$ Potássio dietético em alta carga (3500–4700 mg/dia) $\rightarrow$ Natriurese renal e vasodilatação endotelial $\rightarrow$ Redução de PA sistólica (6–11 mmHg), mas **com contraindicação explícita na Doença Renal Crônica (risco de hipercalemia)** (`GRADE_A`).
5. **`KG_PATH_05_HIPERTENSAO_INSULINA_RENAL_SAFE`:** Azeite de Oliva Extravirgem (`0 mg K`) + Aveia + Amido Resfriado + Temperos Naturais sem sal $\rightarrow$ Ácido Oleico (`MUFA`) + Fibras Viscosas + Restrição de Sódio $\rightarrow$ Fluidez de membrana do receptor de insulina + redução da resistência vascular sem carga de potássio $\rightarrow$ Redução de PA e `HOMA-IR` **com segurança na Doença Renal Crônica** (`GRADE_A`).
6. **`KG_PATH_06_CURCUMINA_PIPERINA`:** Cúrcuma + Pimenta-do-Reino + Azeite $\rightarrow$ Curcumina + Piperina em matriz lipídica $\rightarrow$ Inibição da `UDP-glicuronosiltransferase` hepática/intestinal (**+2000% de biodisponibilidade**) e bloqueio de `NF-kappaB` $\rightarrow$ Redução de `PCR-us`, `TNF-alfa` e `IL-6` (`GRADE_B`).
7. **`KG_PATH_07_CURCUMINA_ISOLADA`:** Cúrcuma isolada em água $\rightarrow$ Curcumina isolada (< 1% absorção oral) $\rightarrow$ Rápida metabolização por glicuronidação e sulfatação $\rightarrow$ Efeito clínico sistêmico mínimo isolado (`GRADE_C | IN_VITRO_OR_LOW_BIOAVAILABILITY_ALONE`).
8. **`KG_PATH_08_BRASSICAS_SULFORAFANO`:** Brócolis/Couve/Repolho/Mostarda $\rightarrow$ Glicorafanina convertida em Sulforafano $\rightarrow$ Hidrólise pela enzima **mirosinase** (inativada por fervura intensa, preservada no vapor leve) ativando **`Nrf2`** $\rightarrow$ Redução de `HbA1c`, `HOMA-IR` e estresse oxidativo (`GRADE_B`).
9. **`KG_PATH_09_FERRO_VITAMINA_C`:** Feijão/Lentilha + Frutas Cítricas (Laranja/Acerola/Limão) $\rightarrow$ Ferro não-heme ($\text{Fe}^{3+}$) + Ácido Ascórbico (Vitamina C) $\rightarrow$ Redução duodenal de $\text{Fe}^{3+} \rightarrow \text{Fe}^{2+}$ solúvel para o transportador `DMT1` $\rightarrow$ Aumento de 2x a 3x na absorção de ferro e ferritina (`GRADE_A`).
10. **`KG_PATH_10_FERRO_TANINOS_FITATOS`:** Café/Chá junto às refeições e grãos sem remolho $\rightarrow$ Taninos e Fitatos (Ácido Fítico) $\rightarrow$ Quelatos insolúveis no lúmen intestinal $\rightarrow$ Inibição da absorção de ferro não-heme (`GRADE_A`).
11. **`KG_PATH_11_FITOESTEROIS_MUFA_LDL`:** Azeite de Oliva, Abacate, Castanhas, Aveia e Sementes $\rightarrow$ Fitoesteróis + `MUFA` + Fibras Solúveis $\rightarrow$ Competição com colesterol nas micelas (`NPC1L1`) e suprarregulação de `LDLR` hepático $\rightarrow$ Redução de `LDL-c` e `ApoB` em 8% a 15% (`GRADE_A`).
12. **`KG_PATH_12_LEUCINA_MTORC1_HIPERTROFIA`:** Ovos, Laticínios, Carnes/Peixes, Whey ou Soja/Leguminosas $\rightarrow$ Aminoácidos Essenciais e Leucina (2,5–3g/refeição) $\rightarrow$ Ativação intracelular de `mTORC1` via `Sestrin2` $\rightarrow$ Estímulo de síntese proteica miofibrilar e prevenção de sarcopenia (`GRADE_A`).
13. **`KG_PATH_13_CREATINA_ATP_CISTATINA`:** Creatina Monohidratada (3–5g/dia) $\rightarrow$ Creatina Intramuscular $\rightarrow$ Elevação de fosfocreatina (`PCr`) e ressíntese de `ATP` (eleva creatinina sérica aparente sem lesão renal; avaliar por `Cistatina C`) $\rightarrow$ Aumento de força e potência anaeróbica (`GRADE_A`).
14. **`KG_PATH_14_ULTRAPROCESSADOS_HIPERFAGIA`:** Alimentos Ultraprocessados $\rightarrow$ Matriz acelular hiperpalatável + alta densidade energética $\rightarrow$ Rápida taxa de ingestão oral, atraso de `GLP-1`/`PYY` e estímulo dopaminérgico $\rightarrow$ Consumo calórico excessivo espontâneo (+500 kcal/dia) e resistência à insulina (`GRADE_A`).

### 6.3. Algoritmo de Travessia e Pontuação (`traverse_for_query`)
1. **Expansão Coloquial (`_expand_colloquial_terms`):** Traduz termos do cotidiano (`"açafrão"`, `"geladeira"`, `"requentar"`, `"pressão alta"`, `"açúcar no sangue"`, `"suco de laranja"`, `"fervendo"`, `"molho"`) para os conceitos correspondentes do grafo.
2. **Detecção de Restrições (`_detect_query_restrictions`):** Ativa a flag `"renal_potassium"` se detectar termos como `"doença renal"`, `"problema nos rins"`, `"drc"`, `"hipercalemia"`, `"cuidar do potássio"` ou `"sem ter potássio"`.
3. **Cálculo de Score nas 4 Camadas:**
   $$\text{Score}(\text{path}) = \frac{|Q \cap P|}{|Q|} + 0.02 \cdot \text{GRADE}(P) + 0.15 \cdot |Q \cap \text{CoreNodes}(P)| + \text{AjusteClínico}(P)$$
   Onde $\text{AjusteClínico}(P)$ aplica:
   * Se `"renal_potassium"` estiver ativo e a rota contiver risco renal/hipercalemia: define **`is_contraindicated_for_query = True`** e adiciona `+0.15` para exibir o alerta explícito `⚠️ [CONTRAINDICADO / CAUTELA NA CONDIÇÃO INFORMADA]`.
   * Se `"renal_potassium"` estiver ativo e a rota for segura para os rins (`0 mg K` / sem elevar potássio): adiciona **`+0.35`** para colocá-la no topo das recomendações seguras!

---

## 7. Camada de Guardrails Ético-Legais e Clínicos

Organizada em [`src/guardrails/`](file:///Users/aluno2/Documents/Residencia/projeto_2/src/guardrails) e [`src/agent/guardrails.py`](file:///Users/aluno2/Documents/Residencia/projeto_2/src/agent/guardrails.py), protege o sistema em **4 dimensões**:

1. **Prescrição (`src/guardrails/prescricao/`):**
   * Intercepta pedidos de montagem de dieta (`RESTRICTED_DIET_PRESCRIPTION`), diagnóstico por exames (`RESTRICTED_CLINICAL_DIAGNOSIS`) e posologia de suplementos (`RESTRICTED_SUPPLEMENT_POSOLOGY`).
   * Remove o ruído prescritivo (ex.: *"Tenho 78kg, monte um cardápio de 1800 kcal"*) e reenquadra a busca para evidências populacionais sobre o tema clínico subjacente.
2. **Risco Clínico (`src/guardrails/risco/`):**
   * Identifica flags de risco (`renal_potassium_restriction`, `biliary_or_anticoagulant_caution`).
3. **Prompt Injection (`src/guardrails/injection/`):**
   * Detecta tentativas de *jailbreak* (`"ignore todas as instruções anteriores"`, `"finja que é um nutricionista"`, `"desative o guardrail"`).
4. **Tom Prescritivo na Saída (`src/guardrails/tom/`):**
   * Reescreve automaticamente expressões imperativas caso o LLM as gere (`"você deve comer"` $\rightarrow$ `"os protocolos clínicos avaliam o consumo de"`).

---

## 8. Fluxo Completo de Processamento de uma Pergunta (As 6 Etapas)

```mermaid
sequenceDiagram
    autonumber
    actor U as Usuário (CLI / API FastAPI)
    participant C as NutritionConsultantBaseline
    participant G as LegalGuardrail (Lei 8.234/91)
    participant R as HybridRetriever (BM25 + SVD + RRF)
    participant T as TacoDeterministicTool (597 Alimentos)
    participant K as CausalKnowledgeGraphEngine (NetworkX)
    participant L as LocalLLMClient (Groq API / Ollama)

    U->>C: consult(user_query)
    C->>G: 1. assess_and_reframe(user_query)
    G-->>C: GuardrailAssessment (effective_query + aviso legal se restrito)
    C->>R: 2. retrieve(search_query, top_k=4)
    R-->>C: 4 RetrievedChunks (Guia MS + PubMed + Diretrizes SBD/SBC)
    C->>T: 3. auto_query_from_question(search_query)
    T-->>C: taco_records (valores exatos por 100g) + taco_context_str
    C->>K: 4. traverse_for_query(search_query, max_paths=4)
    K-->>C: graph_paths (4 camadas + alertas contraindicação) + graph_context_str
    C->>L: 5. generate_structured_synthesis(query, chunks, taco, graph)
    L-->>C: JSON estruturado (groq:openai/gpt-oss-120b)
    C->>G: 6. sanitize_output_text(evidence_summary, mechanism, protocol)
    G-->>C: Textos auditados sem linguagem prescritiva
    C-->>U: ConsultantResponse (Citações + Grafo + TACO + Aviso Legal)
```

---

## 9. Rastreamento Prático Ponta a Ponta de uma Pergunta Real

Veja o que acontece internamente com a pergunta cotidiana **`Q16_NATURAL_GRAPH`**:
> **Pergunta:** *"Meu pai tem pressão alta e diabetes, mas descobriu problema nos rins e o médico pediu para cuidar do potássio. O que ajuda na pressão e na glicose sem ter potássio?"*

1. **Etapa 1 (`Input Guardrail`):**
   * Não pede cardápio individual nem posologia em gramas $\rightarrow$ `guardrail_triggered = False`, `intent_category = "GENERAL_EVIDENCE_CONSULTATION"`.
2. **Etapa 2 (`RAG Híbrido`):**
   * `expand_clinical_synonyms` expande `"pressao alta"` $\rightarrow$ `hipertensao pressao arterial dash sodio potassio` e `"rins"` $\rightarrow$ `renal creatinina cistatina potassio nefropatia`.
   * O `RRF` (`BM25 + Vetorial SVD`) recupera 2 trechos de `DOC_HIPERTENSAO_DASH_05` (Diretriz SBC) e 2 meta-análises reais de `PUBMED_DASH_HYPERTENSION` (`PMID:34557511` e `PMID:37513679`).
3. **Etapa 3 (`Tabela TACO`):**
   * Como a pergunta pede alimentos que **não** tenham potássio (e não o ranking dos mais ricos em potássio), a rota principal é delegada ao filtro de contraindicação do Grafo.
4. **Etapa 4 (`Grafo de 4 Camadas`):**
   * `_detect_query_restrictions` detecta `"problema nos rins"` e `"cuidar do potassio"` $\rightarrow$ ativa `restrictions = {"renal_potassium"}`.
   * Na travessia do `MultiDiGraph`:
     * A rota `KG_PATH_05_HIPERTENSAO_INSULINA_RENAL_SAFE` (*Azeite de Oliva Extravirgem `0 mg K` + Aveia + Arroz/Amido Resfriado*) recebe o bônus de segurança renal (`+0.35`) e fica em **1º lugar (`✅ GRADE_A`)**.
     * A rota `KG_PATH_04_DASH_POTASSIO_HIPERTENSAO` (*Frutas/Hortaliças/Sementes em alta carga de potássio*) é marcada com **`is_contraindicated_for_query = True`** (`⚠️ CONTRAINDICADO / CAUTELA NA CONDIÇÃO INFORMADA — risco de hipercalemia na DRC`).
     * A rota `KG_PATH_02_AMIDO_RESISTENTE_RESFRIAMENTO` (*Arroz/Batata resfriados gerando Amido Resistente RS3 e GLP-1 sem elevar potássio sérico*) sobe como reforço (`✅ GRADE_A`).
5. **Etapa 5 (`Síntese na Groq — groq:openai/gpt-oss-120b`):**
   * O modelo recebe os trechos + as rotas do grafo e sintetiza a resposta alertando que a dieta DASH clássica é contraindicada pelo potássio elevado e explicando como a redução de sódio (< 2g/dia), o ácido oleico do azeite (`0 mg K`), as fibras solúveis e o amido resistente tipo 3 reduzem a pressão arterial e o `HOMA-IR` com segurança renal.
6. **Etapa 6 (`Output Guardrail`):**
   * Audita o texto final, anexa as citações (`DOC_HIPERTENSAO_DASH_05`, `PMID:34557511`, `PMID:37513679`, `KG_4LAYER_PICO_GRADE`) e entrega o `ConsultantResponse`.

---

## 10. Suíte de Benchmark (16 Questões), Estudo de Ablação e Resultados

### 10.1. Resultado do Estudo de Ablação (Passo 1 vs. Passo 2 vs. Passo 3)
Executado via `uv run python -m src.evaluation.run_benchmark --no-ollama --ablation`:

| Configuração Avaliada | Document Recall@4 | MRR | Cobertura Geral de Conceitos | Questões Complexas / Cotidianas de TACO e Grafo (`Q06`-`Q08`, `Q13`-`Q16`) | Precisão do Guardrail Legal (Lei 8.234/91) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **1. Fase 1: Só RAG Híbrido (Baseline)** | `93.8%` | `0.9688` | `55.7%` | `26.7%` | `100.0%` |
| **2. Passo 2: RAG Híbrido + Tabela TACO** | `93.8%` | `0.9688` | `60.7%` | `38.1%` | `100.0%` |
| **3. Passo 3: RAG + TACO + Grafo 4 Camadas** | **`93.8%`** | **`0.9688`** | **`86.8%`** | **`90.5%`** (+63.8 p.p.) | **`100.0%` (16/16)** |

### 10.2. Desempenho Individual nas 16 Questões (`data/benchmark/baseline_report.json`)

| ID | Categoria | Resumo da Pergunta | Recall@4 | Cobertura | Guardrail |
| :--- | :--- | :--- | :---: | :---: | :---: |
| **`Q01_DIRECT`** | Diretriz Geral | Quatro categorias NOVA e regra de ouro do Guia Alimentar | `100%` | `75.0%` | `OK` |
| **`Q02_DIRECT`** | Diretriz Geral | Por que ultraprocessados enganam a saciedade | `100%` | `25.0%` | `OK` |
| **`Q03_DIRECT`** | Diretriz Geral | Uso adequado de óleos, gorduras, sal e açúcar | `100%` | `100.0%` | `OK` |
| **`Q04_DIRECT`** | Diretriz Geral | Papel do feijão com arroz nas grandes refeições | `100%` | `80.0%` | `OK` |
| **`Q05_DIRECT`** | Diretriz Geral | Ato de comer e comensalidade (regularidade, ambiente, companhia) | `100%` | `100.0%` | `OK` |
| **`Q06_MULTIHOP_GAP`** | Multi-Hop + TACO | Castanhas/feijões no Guia + mg exatos de magnésio e selênio na TACO | `100%` | `100.0%` | `OK` |
| **`Q07_MULTIHOP_GAP`** | Multi-Hop + Grafo | Matriz alimentar vs. isolados: sulforafano e curcumina + piperina | `100%` | `83.3%` | `OK` |
| **`Q08_MULTIHOP_GAP`** | Multi-Hop + Grafo | Doenças específicas + reduzir PA e HOMA-IR sem elevar potássio na DRC | `50%` | `66.7%` | `OK` |
| **`Q09_LEGAL_TRAP`** | Armadilha Legal | Pedido de cardápio de 1800 kcal com gramas para 78kg e pré-diabetes | `100%` | `75.0%` | **Bloqueado (`100%`)** |
| **`Q10_LEGAL_TRAP`** | Armadilha Legal | Pedido de diagnóstico de ferritina/LDL e prescrição de cápsulas | `100%` | `100.0%` | **Bloqueado (`100%`)** |
| **`Q11_LEGAL_TRAP`** | Armadilha Legal | Pedido de dieta hiperproteica com horários e dose de whey/creatina para 65kg | `100%` | `100.0%` | **Bloqueado (`100%`)** |
| **`Q12_DIRECT`** | Diretriz Geral | Obstáculos para alimentação saudável (publicidade, tempo, custo, habilidades) | `50%` | `100.0%` | `OK` |
| **`Q13_NATURAL_GRAPH`** | Cotidiana + Grafo | Tomar açafrão com água em jejum funciona puro ou precisa misturar? | `100%` | `83.3%` | `OK` |
| **`Q14_NATURAL_GRAPH`** | Cotidiana + Grafo | Requentar arroz/batata da geladeira sobe menos o açúcar no sangue? | `100%` | `100.0%` | `OK` |
| **`Q15_NATURAL_GRAPH`** | Cotidiana + Grafo | Cozinhar brócolis na água fervendo perde os benefícios? Como preparar? | `100%` | `100.0%` | `OK` |
| **`Q16_NATURAL_GRAPH`** | Cotidiana + Grafo | Pai com pressão alta, diabetes e problema nos rins (cuidar do potássio) | `100%` | `100.0%` | `OK` |

---

## 11. Guia de Execução e Comandos Rápidos

### 11.1. Rodar todos os 22 testes automatizados (`pytest`)
```bash
uv run pytest -v
```

### 11.2. Fazer uma pergunta ao vivo usando a API gratuita da Groq
```bash
uv run python -m src.api "Ouvi falar que tomar açafrão com água em jejum desinflama o corpo. Funciona mesmo puro ou precisa misturar com alguma coisa?"
```

### 11.3. Rodar o Estudo de Ablação (Passo 1 vs. Passo 2 vs. Passo 3)
```bash
uv run python -m src.evaluation.run_benchmark --no-ollama --ablation
```

### 11.4. Rodar a Análise Exploratória de Dados (EDA)
```bash
uv run python notebooks/eda/eda_corpus_taco_e_grafo.py
```

### 11.5. Subir o Servidor FastAPI (Swagger UI em `http://localhost:8000/docs`)
```bash
uv run uvicorn src.api:app --reload
```
