# Relatório Comparativo de Respostas - Split DEV

## Resumo por Condição Experimental

| Condição | N | Correção Factual | Completude | Relevância | Segurança | Fidelidade Contexto | Citações Válidas | Abstenção Adequada | Nota Geral | IC 95% (Incerteza) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `contexto_oracle` | 7 | 100.0% | 13.7% | 52.1% | 71.4% | 1.0 | 1.0 | 57.1% | **0.610** | [0.501, 0.719] |
| `llm_sem_rag` | 7 | 100.0% | 5.5% | 43.6% | 71.4% | N/A | N/A | 57.1% | **0.573** | [0.495, 0.652] |
| `rag_atual` | 7 | 100.0% | 22.0% | 65.1% | 85.7% | 0.49 | 0.857 | 71.4% | **0.685** | [0.563, 0.807] |

## Diagnóstico Secundário de Recuperação (RAG Atual)

> Permite isolar falhas: se a nota for alta no grupo 'com_recuperacao_evidencias', o gerador é fiel quando a busca funciona. Se for baixa mesmo com evidência, o gargalo está na síntese/LLM.

| Cenário de Busca RAG | N | Nota Geral Média | Correção Factual | Completude | Fidelidade ao Contexto |
|---|---:|---:|---:|---:|---:|
| `Evidências recuperadas no top-k` | 5 | **0.731** | 100.0% | 30.8% | 68.7% |
| `Falha na recuperação de evidências` | 2 | **0.570** | 100.0% | 0.0% | 0.0% |

## Confrontos Diretos Pareados (Head-to-Head)

| Confronto | Vitórias C1 | Vitórias C2 | Empates |
|---|---:|---:|---:|
| `contexto_oracle_vs_llm_sem_rag` | 2 | 0 | 5 |
| `contexto_oracle_vs_rag_atual` | 0 | 3 | 4 |
| `llm_sem_rag_vs_rag_atual` | 0 | 4 | 3 |
