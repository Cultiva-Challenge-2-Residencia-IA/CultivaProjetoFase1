# Repo audit

## Estado atual observado

- Branch: `developingrid` com 1 commit à frente do remoto.
- Arquivos alterados antes do trabalho: `corpus/scripts/converter_pdf_nutricao.py` e exclusões em `src/agents/nutricao/*`.
- Arquivos não rastreados: `.DS_Store`, `corpus/.DS_Store`, `src/.DS_Store`.
- O repositório está em scaffold inicial: README mínimo, `corpus/` com 3 fontes, `docs/` com PDFs e `specs/` vazia.

## Árvore relevante

```text
.
├── README.md
├── corpus/
│   ├── manifest.yaml
│   ├── nutricao/
│   │   ├── AguaHidratacaoESaude.md
│   │   ├── DepressaoAnsiedadeEstresseAlimentacao.md
│   │   └── posicionamento_2022-alterado-nov-22-1.md
│   └── scripts/
│       └── converter_pdf_nutricao.py
├── docs/
│   ├── adrs/
│   ├── nutricao/
│   │   ├── AguaHidratacaoESaude.pdf
│   │   ├── DepressaoAnsiedadeEstresseAlimentacao.pdf
│   │   └── posicionamento_2022-alterado-nov-22-1.pdf
│   ├── ripd/
│   └── rubric/
├── eval/
│   ├── golden/
│   └── runs/
├── infra/
├── notebooks/
│   └── eda/
├── specs/
├── src/
│   ├── agents/
│   ├── api/
│   ├── broker/
│   ├── guardrails/
│   └── rag/
└── .git/
```

## O que será adicionado

- `AGENTS.md`
- `.claude/skills/*/SKILL.md`
- `specs/constitution.md`
- `specs/traceability.md`
- `specs/nutricao/*.md`
- `specs/nutricao/contracts/*`
- `specs/nutricao/features/*.feature`
- `docs/architecture.md`, `docs/corpus.md`, `docs/evaluation.md`, `docs/safety.md`, `docs/backlog.md`
- `docs/adr/*.md`
- `CHANGELOG.md`, `.env.example`, `Makefile`

## Conflitos e riscos

1. O repo já tem alterações locais e exclusões em `src/agents/nutricao`; a entrega deve preservar o estado atual e acrescentar arquivos novos sem remover conteúdo existente.
2. O diretório `docs/nutricao` guarda PDFs que parecem ser fontes de referência, mas não devem ser tratados como fonte autorizada de fatos sem checar o manifesto e as fontes listadas.
3. O manifesto atual está vazio e exige um `sources.yaml`/manifesto de ingestão conforme o requisito RN16.
4. O projeto ainda não define uma convenção de skills; a solução escolhida é `.claude/skills` por padrão.

## Regra de preservação aplicada

Conforme R1, não foram apagados, movidos, renomeados ou sobrescritos arquivos existentes. Onde houve conflito de estrutura, foi optado por extensão e criação de novos artefatos com sufixo de documentação ou arquivo novo, sem matar o que já existe.
