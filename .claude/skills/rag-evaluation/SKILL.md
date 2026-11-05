---
name: rag-evaluation
description: Use when benchmarking retrieval, groundedness, safety, latency, and the golden-set workflow for the nutrition slice.
---
# rag-evaluation

## Quando usar

- a qualidade da recuperação precisa ser medida
- a geração precisa validar groundedness e citação
- há necessidade de baseline, golden set ou relatório

## Regras

- sempre compare contra baseline
- não usar LLM-as-judge como único critério
- falhe em métrica crítica quando estiver acima do limite de regressão
- mantenha 20% de revisão humana em amostra

## Passos

1. preparar golden set
2. rodar recuperação sem LLM
3. medir segurança e groundedness
4. comparar latência e métricas
5. gerar relatório em JSON/Markdown

## Checklist

- medidas de recuperação coletadas
- golden set válido
- baseline registrada
- revisão humana planejada

## Erros comuns

- medir apenas geração sem recuperar primeiro
- ignorar segurança no benchmark
- declarar sucesso sem baseline e métrica de regressão
