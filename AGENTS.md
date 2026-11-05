# AGENTS.md

## Visão

CULTIVA é um app focado em nutrção, saúde física e estudos, com IA orientada a educação, organização e autocuidado. A frente de nutrição deve trabalhar com base documental, evidência e guardrails de segurança. O objetivo principal é responder com fontes e suportar decisões simples e sustentáveis sem substituir profissionais.

## Comandos

- `git status`
- `git diff --stat`
- `make setup`
- `make up`
- `make ingest`
- `make test`
- `make eval`
- `make lint`

## Regras obrigatórias

- R1: não apagar, mover, renomear ou sobrescrever conteúdo existente; em conflito, estender ou criar `*.proposed` ao lado e registrar em `docs/repo-audit.md`.
- R2: não inventar fatos. Metadado desconhecido deve ser `null` e precisa ser registrado em `docs/assumptions.md`.
- R3: cada mudança deve seguir spec → plano → tarefas → teste → código; se o código divergir, a spec deve ser atualizada no mesmo commit.
- R4: segurança tem prioridade.
- R5: dependências travadas, temperatura 0, seeds fixas, modelos e prompts versionados.
- R6: medir antes de otimizar; reranker e query rewrite só entram se a avaliação provar ganho.
- R7: documentação e interface em pt-BR; código no padrão do repo.
- R8: commits pequenos e etapa por etapa na branch `feat/nutricao-rag-mvp`.

## Mapa de skills

- `sdd-workflow`: iniciar e manter a documentação de arquitetura e requisitos.
- `rag-ingestion`: ingestão, manifesto, hash e chunking.
- `rag-retrieval`: busca híbrida, gate de evidência e query rewrite.
- `grounded-generation`: geração com fontes e groundedness.
- `safety-guardrails-nutricao`: recusa, risco, escopo e prompt injection.
- `rag-evaluation`: golden set, métricas e relatórios.
- `langgraph-orchestration`: grafo e estado.

## Specs e documentação

- `specs/constitution.md`
- `specs/traceability.md`
- `specs/nutricao/spec.md`
- `specs/nutricao/plan.md`
- `specs/nutricao/tasks.md`
- `specs/nutricao/data-model.md`
- `specs/nutricao/quickstart.md`
- `specs/nutricao/contracts/`
- `docs/architecture.md`
- `docs/backlog.md`
- `docs/safety.md`
- `docs/evaluation.md`

## Observações

- Fase 0 concluída como descoberta sem código.
- Fase 1 entregue para aprovação antes de implementação.
- Implementação de código, testes e infraestrutura começa somente após aprovação da spec.
