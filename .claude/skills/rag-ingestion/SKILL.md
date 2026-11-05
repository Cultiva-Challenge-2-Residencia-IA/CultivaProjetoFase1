---
name: rag-ingestion
description: Use when ingesting corpus, building source manifests, cleaning raw text, and chunking documents for retrieval.
---
# rag-ingestion

## Quando usar

- há corpus em Markdown/PDF e falta ingestão
- o projeto precisa de whitelist, hash e chunking
- a base precisa ser idempotente e rastreável

## Regras

- usar whitelist estrita
- nunca inventar metadados
- preservar `source_id`, `section`, `page`, `corpus_version`
- não cortar listas, tabelas ou parágrafos importantes

## Passos

1. mapear fontes e metadados
2. limpar páginas, cabeçalhos e rodapés
3. segmentar por estrutura
4. gerar `chunk_id` e `corpus_manifest.json`
5. validar idempotência e reingestão incremental

## Checklist

- fonte autorizada
- chunk estável
- sem duplicação indevida
- manifesto atualizado

## Erros comuns

- quebrar tabela ou lista no meio
- aceitar fonte fora da whitelist
- gerar chunk sem texto contextual
