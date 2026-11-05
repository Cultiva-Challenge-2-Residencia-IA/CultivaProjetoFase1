# ADR 0003: fallback InMemoryStore para testes e ambientes sem Docker

## Status

Aceito.

## Contexto

O repositório deve manter execução em CI e ambientes locais sem depender de Postgres + pgvector sempre disponível.

## Decisão

Implementar `VectorStore` com `PgVectorStore` como padrão e `InMemoryStore` como fallback para testes, dev local e ambientes sem Docker.

## Consequências

- melhora reprodutibilidade
- permite validação sem infraestrutura pesada
- reduz risco de CI quebrando por ausência de serviço externo
- requer equivalência de semântica em testes de integração
