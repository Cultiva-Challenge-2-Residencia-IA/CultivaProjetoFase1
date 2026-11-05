# ADR 0001: priorizar recuperação antes da geração

## Status

Aceito.

## Contexto

Na frente de nutrição, a maior parte das respostas ruins vem de recuperação ruim. O no-code/riscado de confiar no modelo para corrigir rastreio tem efeito negativo em groundedness.

## Decisão

A implementação deve priorizar M1 (ingestão + recuperação + métricas de recuperação) antes de M2 (geração). A busca híbrida deve ser a base da evidência.

## Consequências

- melhora no groundedness
- redução de afirmações sem suporte
- maior necessidade de benchmark e avaliação de retrieval
- demora mais para entrar na geração, mas com menos risco de erro
