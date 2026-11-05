---
name: sdd-workflow
description: Use when starting or revising specs, plans, tasks, and traceability for a delivery and when product work must stay spec-anchored.
---
# sdd-workflow

## Quando usar

- o trabalho exige spec → plano → tarefas → testes → código
- a equipe precisa manter requisitos rastreáveis e coerentes
- o projeto está em fase de arquitetura ou revisão

## Regras

- não implemente sem requisito e critério de aceite
- mantenha `constitution.md` e `traceability.md` atualizados
- se houver divergência, ajuste a spec no mesmo commit
- cada requisito precisa ter origem, módulo e teste

## Passos

1. listar requisitos e riscos
2. mapear arquitetura com fluxo e decisões
3. dividir em marcos (M1-M5)
4. definir testes de aceite antes do código
5. documentar `assumptions.md` e ADRs

## Checklist

- requisitos descritos
- critérios mensuráveis
- rastreabilidade preenchida
- riscos e hipóteses registrados

## Erros comuns

- pular requisito e começar no código
- deixar requisito órfão
- documentar sem provas e sem teste
