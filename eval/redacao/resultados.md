# Redação final e esclarecimento (issue #104): resultados

Critérios em [`criterios.md`](criterios.md), escritos e commitados antes de medir. `gemma4:e4b` local; o `dev` foi medido na RTX 5060 (25/11/2026) e o `test` na GTX 1650 (26/11/2026), por isso os tempos dos dois não se comparam entre si; cada comparação com e sem redação é na mesma placa. Juízes: subagentes do Claude, sem acesso ao código; um julga a utilidade (pares A/B em ordem sorteada, sem saber qual é a redigida) e outro o exagero (reescrita contra o texto checado de origem). O par sai da mesma execução (texto antes e depois da redação).

| Medida | Critério | `dev` | `test` (uma vez) |
|---|---|---:|---:|
| Aceitação da redação | ≥ 0,70 | 0,571 (4 de 7) | **0,800** (4 de 5) |
| Utilidade: a redigida vence | ≥ 60% dos pares sem empate | 100% (4 de 4) | **100%** (4 de 4) |
| Exagero: frases além da origem | ≤ 10% | 18,8% (3 de 16) | **10,0%** (1 de 10) |
| Latência: mediana com / sem redação | ≤ 1,4× | 17,9 s / 16,7 s | 41,0 s / 48,3 s |
| Esclarecimento nos vagos / nos demais | ≥ 0,70 / ≤ 0,10 | 0,5 / 0,0 | **1,0 / 0,0** |

**Decisão:** pela regra de `criterios.md`, utilidade e exagero cumpridos no `test` deixam a redação **ligada por padrão** (`CULTIVA_REDACAO=true`).

## Como ler

- **Amostra pequena:** 4 pares e 10 frases no `test`. O exagero ficou exatamente no limite (1 frase de 10): "As orientações básicas sugerem comer com regularidade e atenção, o que **ajuda a controlar** melhor a quantidade que se come", uma relação que a origem não faz.
- **O `dev` não cumpriu** aceitação (0,571), exagero (18,8%) e esclarecimento (0,5). Nenhum ajuste foi feito entre o `dev` e o `test`. Os exageros do `dev` são do mesmo tipo: relação de causa ou generalização além da origem (ex.: "comer em companhia ajuda a criar um ambiente apropriado").
- **A checagem por código** pega número, unidade e fonte inventados; o exagero de sentido só é pego por julgamento. Um prompt mais restrito contra relações de causa fica como próximo passo na issue "Qualidade das respostas do chat: régua de perguntas reais e correção das causas" (#118).
- **Utilidade:** nos dois splits, o juiz preferiu a redigida em todos os pares sem empate, porque ela começa pela resposta e tira dados soltos. Em duas perguntas do `test` ("Refrigerante zero é melhor?", "Comer à noite engorda?"), o juiz notou que **nenhuma** das versões responde de fato: a redação melhora a forma, não o conteúdo recuperado (issue #118).
- Os casos têm o mesmo autor do código.
