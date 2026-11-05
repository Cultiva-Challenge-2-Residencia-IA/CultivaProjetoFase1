# Quickstart

## Ambiente

- Python 3.11+
- Docker para Postgres + pgvector
- `uv` ou `pip` para dependências
- `.env` com versões fixas

## Passos

1. Copiar `.env.example` para `.env`.
2. Rodar `make setup`.
3. Rodar `make up`.
4. Rodar `make ingest`.
5. Validar com `make test`.
6. Executar `make eval` para relatório final.

## Verificações obrigatórias

- `GET /health` responde 200.
- `POST /v1/nutricao/perguntar` retorna `answer`, `claims`, `sources`, `trace_id`.
- `trace_id` contém versão de prompt, modelo e corpus.
- Qualquer resposta sem fonte vira `não sei`.
