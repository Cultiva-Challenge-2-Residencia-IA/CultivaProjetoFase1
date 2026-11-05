# Arquitetura

## Contexto

A frente de nutrição do CULTIVA é um pipeline orientado a evidência com 5 camadas: ingestão, recuperação, geração, guardrails e rastreio.

## Camadas

- Ingestão: manifesto, whitelist, parser, chunking e hashing.
- Recuperação: busca híbrida, RRF, gate de evidência.
- Geração: prompt versionado, grounded check, respostas estruturadas.
- Guardrails: risco, escopo, prompt injection, saída e privacidade.
- Observabilidade: JSONL trace, latência e resposta final.

## Componentes centrais

- `sources.yaml` e `corpus_manifest.json`
- `VectorStore` e `Embedder`
- `LLMClient` com `FakeLLM` para CI
- `Tracer` com `JsonlTracer`
- LangGraph com nós `risk_gate`, `scope_gate`, `retrieve`, `generate`, `assemble`

## Decisão principal

A arquitetura prioriza a recuperação e validação antes da geração. Isso reduz ruído do corpus e evita respostas sem sustentação.
