# Relatório Comparativo de Respostas - Split TEST

## Resumo por Condição Experimental

| Condição | N | Correção Factual | Completude | Relevância | Segurança | Fidelidade Contexto | Citações Válidas | Abstenção Adequada | Nota Geral |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `contexto_oracle` | 6 | 83.3% | 16.7% | 53.1% | 91.7% | 1.0 | 1.0 | 83.3% | **0.605** |
| `llm_sem_rag` | 6 | 100.0% | 0.0% | 44.0% | 66.7% | N/A | N/A | 50.0% | **0.548** |
| `rag_atual` | 6 | 100.0% | 27.8% | 63.8% | 91.7% | 0.608 | 1.0 | 83.3% | **0.712** |

## Confrontos Diretos Pareados (Head-to-Head)

| Confronto | Vitórias C1 | Vitórias C2 | Empates |
|---|---:|---:|---:|
| `contexto_oracle_vs_llm_sem_rag` | 3 | 1 | 2 |
| `contexto_oracle_vs_rag_atual` | 0 | 1 | 5 |
| `llm_sem_rag_vs_rag_atual` | 0 | 4 | 2 |
