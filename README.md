# CULTIVA

Projeto de IA aplicada a nutrição, saúde física e estudos para jovens adultos e estudantes brasileiros.

## Visão

CULTIVA apoia a transformação de bons hábitos em decisões simples e sustentáveis, sem substituir o profissional. A frente de nutrição é a primeira entrega e deve operar com rigor científico, fontes verificáveis e guardrails de segurança.

## Escopo da entrega atual

- Nutrição apenas.
- RAG inicial sobre o corpus existente.
- Agente orquestrado com respostas fundamentadas.
- Guardrails de risco, escopo e prompt injection.
- Avaliação do fluxo e documentação técnica.

## Regras primárias

- Nenhuma resposta pode substituir profissional.
- Nenhum fato sem base no corpus.
- Respostas em pt-BR.
- Fonte obrigatória ou resposta `não sei`.
- Segurança acima de qualquer outra otimização.

## Estrutura

- `corpus/`: material bruto e manifesto do corpus.
- `docs/`: relatórios, ADRs, backlog e documentação técnica.
- `specs/`: constituição, rastreabilidade e especificação da frente de nutrição.
- `src/`: implementação do agente e módulos de RAG/guardrails.
- `eval/`: golden set e relatórios de avaliação.

## Guia de contribuição

1. Ler a constituição e a spec de nutrição em `specs/`.
2. Fazer mudanças alinhadas às tarefas da Fase 1.
3. Validar com `make test` e `make eval` quando a implementação estiver pronta.
4. Manter rastreabilidade dos requisitos em `specs/traceability.md`.

## Observações

- O repositório ainda preserva artefatos existentes e não remove conteúdo legado.
- O desenvolvimento segue a branch `feat/nutricao-rag-mvp` e a documentação de arquitetura e risco deve ser mantida em português.
