# Relatório Comparativo de Respostas - Split DEV

## Resumo por Condição Experimental

| Condição | N | Correção Factual | Completude | Relevância | Segurança | Fidelidade Contexto | Citações Válidas | Abstenção Adequada | Nota Geral |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `contexto_oracle` | 7 | 100.0% | 0.0% | 42.0% | 71.4% | 0.0 | 1.0 | 57.1% | **0.554** |
| `llm_sem_rag` | 7 | 100.0% | 0.0% | 42.0% | 71.4% | N/A | N/A | 57.1% | **0.554** |
| `rag_atual` | 7 | 100.0% | 22.0% | 65.7% | 92.9% | 0.304 | 0.857 | 85.7% | **0.700** |

## Confrontos Diretos Pareados (Head-to-Head)

| Confronto | Vitórias C1 | Vitórias C2 | Empates |
|---|---:|---:|---:|
| `contexto_oracle_vs_llm_sem_rag` | 0 | 0 | 7 |
| `contexto_oracle_vs_rag_atual` | 0 | 5 | 2 |
| `llm_sem_rag_vs_rag_atual` | 0 | 5 | 2 |
