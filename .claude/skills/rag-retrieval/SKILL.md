---
name: rag-retrieval
description: Use when building hybrid search, ranking, evidence gates, and retrieval metrics before any generation step.
---
# rag-retrieval

## Quando usar

- a busca precisa priorizar evidência sobre prompt
- a etapa de recuperação ainda não está validada
- o projeto precisa de recall/precision e gate de evidência

## Regras

- medir antes de otimizar
- no mínimo, usar busca híbrida e RRF
- responder `não sei` se o melhor trecho está abaixo do limiar
- query rewrite só com histórico real

## Passos

1. gerar embeddings e índice lexical
2. buscar denso + lexical
3. combinar via RRF
4. aplicar threshold e top-k
5. reportar métricas Recall@5/MRR/nDCG@5

## Checklist

- top-k definido
- threshold calibrado
- metricas registradas
- resposta sem evidência é `não sei`

## Erros comuns

- ajustar LLM antes do retriever
- usar reranker sem medir ganho
- deixar responder mesmo sem evidência
