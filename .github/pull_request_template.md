<!--
Título: Conventional Commits em português, por exemplo "feat(rag): responde 'não sei' fora do domínio".
Tipos usados aqui: feat, fix, docs, refactor, test, chore, ci, eval.
-->

## Contexto

<!-- Que problema este PR resolve. -->

Closes #

<!-- Use "Refs #N" se o PR não fecha a issue inteira, e diga o que falta. -->

## O que muda

-

## Impacto

<!--
Se o PR pode mudar respostas, recuperação ou guardrails, mostre as métricas antes e depois
(benchmark v1, golden set v2, risco, abstenção), inclusive as que pioraram.
Se não muda nada disso, escreva "Sem efeito nas respostas".
-->

| Métrica | Antes (`main`) | Depois |
|---|---:|---:|
|  |  |  |

## Limitações

<!-- O que não foi resolvido, o que ficou como hipótese e o que precisa de outra pessoa para validar. -->

## Verificação

- [ ] `uv run ruff check .`
- [ ] `uv run pytest -q`
- [ ] Mudou o corpus, o manifesto, o `prepare_rag.py` ou o `rag.yaml`: Trechos regenerados no mesmo PR e `verify_corpus.py` passando
- [ ] Pode mudar respostas: benchmark rodado duas vezes com relatórios idênticos, e `gate.py` sem falhas novas
- [ ] Métricas mudaram de propósito: `eval/baselines/benchmark_offline.json` atualizado, com a justificativa acima
- [ ] Ajustes feitos só no `dev`; o `test` e os holdouts (`eval/risco/holdout.json`) não orientaram a mudança
- [ ] Documentação atualizada (`CLAUDE.md`, `AGENTS.md`, READMEs ou `docs/`), se o comportamento mudou
- [ ] Sem dados pessoais reais, segredos ou endereços de infraestrutura no código, nos testes ou nos casos de avaliação
