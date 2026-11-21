# Relatório Comparativo de Respostas - Split DEV

## Resumo por Condição Experimental

| Condição | Modelo Utilizado | N (falhas) | Correção Factual | Completude | Relevância | Segurança (Lei 8.234) | Fidelidade Contexto | Citações Válidas | Abstenção Adequada | Nota Geral | IC 95% (t-Student) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `contexto_oracle` | `gemma4:e4b` | 36 (0) | 61.4% | 51.0% | 59.3% | 77.8% | 0.603 | 1.0 | 77.8% | **0.613** | [0.498, 0.727] |
| `llm_sem_rag` | `gemma4:e4b` | 36 (0) | 56.0% | 41.6% | 65.9% | 80.6% | N/A | N/A | 80.6% | **0.581** | [0.480, 0.682] |
| `rag_atual` | `local_extractive_synthesis`, `mensagem_fixa`, `ollama:gemma4:e4b` | 36 (0) | 62.5% | 42.8% | 59.9% | 83.3% | 0.429 | 0.167 | 83.3% | **0.604** | [0.497, 0.710] |
| `rag_extrativo` | `sintese-extrativa-deterministica` | 36 (0) | 50.2% | 31.8% | 56.8% | 80.6% | 0.774 | 0.0 | 80.6% | **0.517** | [0.411, 0.624] |

N conta só as execuções em que a condição foi de fato medida. As falhas (o LLM não respondeu, por erro ou tempo esgotado) ficam de fora da nota e aparecem entre parênteses.

## Composição das execuções

| Condição | Modelos (execuções) | Status da síntese (rag_atual) |
|---|---|---|
| `contexto_oracle` | `gemma4:e4b`: 36 | — |
| `llm_sem_rag` | `gemma4:e4b`: 36 | — |
| `rag_atual` | `local_extractive_synthesis`: 1, `mensagem_fixa`: 6, `ollama:gemma4:e4b`: 29 | `extrativa_apos_citacao_invalida`: 1, `llm_citacoes_validas`: 29, `llm_sem_base`: 2 |
| `rag_extrativo` | `sintese-extrativa-deterministica`: 36 | — |

## Diagnóstico Secundário de Recuperação (RAG Atual)

> Compara o RAG quando o buscador recupera trechos úteis vs quando falha em recuperar, isolando o erro do retriever do erro de síntese generativa da LLM.

| Cenário de Busca RAG | N | Nota Geral Média | Correção Factual | Completude | Fidelidade ao Contexto |
|---|---:|---:|---:|---:|---:|
| `Evidências recuperadas no top-k` | 30 | **0.676** | 68.3% | 51.3% | 31.4% |
| `Falha na recuperação de evidências` | 6 | **0.241** | 33.3% | 0.0% | 100.0% |

## Confrontos Diretos Pareados (Head-to-Head)

| Confronto | Vitórias C1 | Vitórias C2 | Empates |
|---|---:|---:|---:|
| `contexto_oracle_vs_llm_sem_rag` | 9 | 6 | 21 |
| `contexto_oracle_vs_rag_atual` | 8 | 6 | 22 |
| `contexto_oracle_vs_rag_extrativo` | 11 | 2 | 23 |
| `llm_sem_rag_vs_rag_atual` | 10 | 11 | 15 |
| `llm_sem_rag_vs_rag_extrativo` | 13 | 7 | 16 |
| `rag_atual_vs_rag_extrativo` | 8 | 2 | 26 |

## Diferença da nota geral entre condições (bootstrap pareado)

Diferença média caso a caso (C1 menos C2), com IC 95% por bootstrap pareado (10.000 reamostras). Intervalo com o zero é empate técnico.

| Comparação | N | Diferença | IC 95% | Leitura |
|---|---:|---:|---|---|
| `contexto_oracle_vs_llm_sem_rag` | 36 | +0.032 | [-0.054; +0.115] | empate técnico |
| `contexto_oracle_vs_rag_atual` | 36 | +0.009 | [-0.066; +0.083] | empate técnico |
| `contexto_oracle_vs_rag_extrativo` | 36 | +0.095 | [+0.020; +0.170] | diferença real |
| `llm_sem_rag_vs_rag_atual` | 36 | -0.023 | [-0.124; +0.080] | empate técnico |
| `llm_sem_rag_vs_rag_extrativo` | 36 | +0.064 | [-0.043; +0.168] | empate técnico |
| `rag_atual_vs_rag_extrativo` | 36 | +0.086 | [+0.030; +0.152] | diferença real |
