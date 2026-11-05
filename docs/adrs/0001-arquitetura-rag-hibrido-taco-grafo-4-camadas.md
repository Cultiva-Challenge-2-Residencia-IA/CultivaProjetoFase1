# ADR 0001: Arquitetura em 3 Passos (RAG Híbrido + Ferramenta TACO + Grafo Causal de 4 Camadas)

* **Status:** Aceito e Implementado
* **Data:** 2026-11
* **Escopo:** Módulo de Nutrição Baseada em Evidências (`CultivaProjetoFase1`)

## 1. Contexto e Problema
Sistemas de IA para dúvidas de nutrição enfrentam três riscos críticos:
1. **Risco Ético-Legal:** Violar a **Lei Federal nº 8.234/1991 (Art. 3º, VIII - CFN)** ao prescrever dietas, cardápios ou doses individualizadas.
2. **Alucinação Quantitativa:** LLMs erram valores numéricos de composição de alimentos brasileiros quando consultados sem uma ferramenta determinística.
3. **Falha em Raciocínio Multi-Hop e Contraindicações Cruzadas:** Um RAG textual puro recomenda alimentos ricos em potássio (padrão DASH) para hipertensão mesmo quando o usuário relata Doença Renal Crônica (risco de hipercalemia).

## 2. Decisão Arquitetural
Adotamos uma arquitetura neuro-simbólica determinística em **3 Passos**, integrada à API gratuita **Groq (`openai/gpt-oss-120b` / `qwen/qwen3.8-27b`)**:

1. **Passo 1 (RAG Híbrido Multi-Documento + Guardrail Legal):**
   * `BM25Okapi` (léxico biomédico) + `TF-IDF/TruncatedSVD` (vetorial denso local) fundidos via **Reciprocal Rank Fusion (RRF)** + Reranker Clínico `GRADE` + Diversificação Documental (`MAX_CHUNKS_PER_DOC=2`).
2. **Passo 2 (Ferramenta Determinística Tabela TACO 4ª Edição - Unicamp):**
   * Consulta exata e ordenação matemática por `100g` sobre os **597 alimentos oficiais**.
3. **Passo 3 (Grafo Causal Controlado de 4 Camadas em `NetworkX`):**
   * Topologia estrita: `FOOD ➔ COMPOUND ➔ MECHANISM ➔ OUTCOME (PICO/GRADE)`, validando sinergias de biodisponibilidade (`LOW_EFFICACY_ALONE`) e contraindicações clínicas (`is_contraindicated_for_query`).

## 3. Consequências e Resultados Empíricos (Estudo de Ablação)
* **Document Recall@4:** `93.8%`
* **Cobertura em Questões Complexas Multi-Hop/TACO/Grafo:** Subiu de `26.7%` (só RAG) para `38.1%` (+ TACO) e atingiu **`90.5%`** (+ Grafo de 4 Camadas).
* **Precisão do Guardrail Legal (Lei 8.234/91):** `100.0% (16/16)`.
