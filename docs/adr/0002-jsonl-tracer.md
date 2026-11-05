# ADR 0002: rastrear em JSONL local

## Status

Aceito.

## Contexto

RNF08 exige rastreabilidade em 100% das respostas. O ambiente do slice 1 deve ser simples e reproduzível, sem colocar Langfuse como dependência obrigatória.

## Decisão

Usar `JsonlTracer` em `var/traces/` atrás de `Tracer`, com `trace_id`, prompt versionado, modelo, embedding, corpus_version, trechos e latência por nó.

## Consequências

- rastreia todas as respostas sem serviço extra
- atende RNF08 com baixo custo operacional
- facilita a auditoria em avaliação e testes
- exige disciplina de mascaramento e versionamento de prompt/modelo
