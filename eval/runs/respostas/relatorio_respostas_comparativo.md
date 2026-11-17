# Relatório Comparativo de Respostas - Split DEV

## Resumo por Condição Experimental

| Condição | Modelo Utilizado | N | Correção Factual | Completude | Relevância | Segurança (Lei 8.234) | Fidelidade Contexto | Citações Válidas | Abstenção Adequada | Nota Geral | IC 95% (t-Student) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `contexto_oracle` | `qwen2.5:3b` | 20 | 45.6% | 9.3% | 60.4% | 75.0% | 0.312 | 1.0 | 75.0% | **0.428** | [0.312, 0.545] |
| `llm_sem_rag` | `fallback-erro-ollama`, `qwen2.5:3b` | 20 | 37.9% | 1.5% | 65.9% | 80.0% | N/A | N/A | 80.0% | **0.396** | [0.295, 0.498] |
| `rag_atual` | `local_extractive_synthesis`, `mensagem_fixa`, `ollama:qwen2.5:3b` | 20 | 53.0% | 19.7% | 63.1% | 75.0% | 0.377 | 0.2 | 75.0% | **0.489** | [0.358, 0.620] |
| `rag_extrativo` | `sintese-extrativa-deterministica` | 20 | 26.8% | 4.7% | 53.9% | 65.0% | 0.783 | 0.0 | 65.0% | **0.319** | [0.208, 0.430] |

## Diagnóstico Secundário de Recuperação (RAG Atual)

> Compara o RAG quando o buscador recupera trechos úteis vs quando falha em recuperar, isolando o erro do retriever do erro de síntese generativa da LLM.

| Cenário de Busca RAG | N | Nota Geral Média | Correção Factual | Completude | Fidelidade ao Contexto |
|---|---:|---:|---:|---:|---:|
| `Evidências recuperadas no top-k` | 16 | **0.528** | 53.7% | 24.7% | 22.1% |
| `Falha na recuperação de evidências` | 4 | **0.336** | 50.0% | 0.0% | 100.0% |

## Confrontos Diretos Pareados (Head-to-Head)

| Confronto | Vitórias C1 | Vitórias C2 | Empates |
|---|---:|---:|---:|
| `contexto_oracle_vs_llm_sem_rag` | 4 | 3 | 13 |
| `contexto_oracle_vs_rag_atual` | 2 | 7 | 11 |
| `contexto_oracle_vs_rag_extrativo` | 7 | 2 | 11 |
| `llm_sem_rag_vs_rag_atual` | 3 | 9 | 8 |
| `llm_sem_rag_vs_rag_extrativo` | 7 | 3 | 10 |
| `rag_atual_vs_rag_extrativo` | 9 | 0 | 11 |
