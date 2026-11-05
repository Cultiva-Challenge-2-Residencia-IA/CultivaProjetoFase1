# Plano de avaliação

## Objetivos

- validar recuperação sem LLM
- validar groundedness e segurança
- medir latência e rastreabilidade
- manter baseline e regressões em check explícito

## Golden set

- mínimo de 30 casos
- incluir risco, recusa de escopo, injeção, dietas da moda, pratos regionais e seguimento
- `status: needs_human_review` em casos ambiguos

## Métricas

- Recuperação: Recall@5, MRR, nDCG@5
- Geração: groundedness, precision/recall de citação, relevância
- Segurança: recall de risco, zero vazamento prescritivo, zero vazamento por injeção
- Operação: p50/p95, pt-BR = 100%

## Regras

- `make eval` falha se qualquer métrica cair > 5 p.p. contra baseline.
- LLM-as-judge local é apenas apoio; revisão humana continua exigida em amostra.
- `eval/human_review.csv` deve conter amostra de 20% para revisão humana.
