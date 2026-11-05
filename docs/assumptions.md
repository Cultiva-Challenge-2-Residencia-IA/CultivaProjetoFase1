# Assumptions

Este documento registra as premissas adotadas para evitar bloqueios durante a Fase 0 e a Fase 1.

- Não foi encontrado arquivo `docs/CULTIVA___PRINCIPAL*` no repositório; assume-se que o material principal não foi anexado e a base de verdade para a entrega é o corpus em `corpus/nutricao`.
- O projeto usa Git com branch `developingrid` e implantação em um scaffold estático; a convenção de skill adotada será `.claude/skills` porque não existe outra convenção no repo.
- O manifesto atual em `corpus/manifest.yaml` está vazio; assumi que a ingestão do corpus requer um `sources.yaml` e `corpus_manifest.json` gerados em Fase 2, sem inventar dados de fontes.
- `docs/nutricao/*.pdf` são artefatos auxiliares e não substituem a operação de ingestão do texto bruto em Markdown.
- O idioma de interface e documentação será português brasileiro; nomes de classes, módulos e variáveis em código seguirão a convenção do repo quando existir, e inglês quando não existir.
- A obra de nutrição precisa seguir estritamente as regras do prompt; nenhuma afirmação fora do corpus será adicionada sem explicitamente declarar o item em `docs/assumptions.md`.
- O uso de `Langfuse` e `Redis` permanece no backlog conforme a decisão do prompt.
- O ambiente de execução ainda não foi validado para Docker/Postgres; o design mantém `InMemoryStore` em fallback para testes.
