# Comparação de frameworks de guardrail (issue #52): resultados

Gerado por `uv run python -m src.evaluation.comparacao_guardrails relatorio`. Não edite à mão.

Modelo: `gemma4:e4b` · máquina: referência · critérios: [`criterios.md`](criterios.md).
Entre colchetes, o intervalo de Wilson de 95%.

## "Não sei"

| Camada | Nutrição fora do corpus (test) | Nutrição fora do corpus (todos) | Fora de Nutrição | Recusa indevida (golden v2) | Recusa indevida (abstenção, todos) | Tempo p50 / p95 (s) | Chamadas |
|---|---|---|---|---|---|---|---:|
| Só camadas locais | 1/6 (17%) [3%; 56%] | 6/28 (21%) [10%; 40%] | 24/26 (92%) [76%; 98%] | 1/31 (3%) [1%; 16%] | 0/42 (0%) [0%; 8%] | 0 | 0 |
| `direto_pre` | 6/6 (100%) [61%; 100%] | 22/28 (79%) [60%; 90%] | 26/26 (100%) [87%; 100%] | 11/31 (35%) [21%; 53%] | 9/42 (21%) [12%; 36%] | 0.43 / 0.54 | 1.0 |
| `direto_pos` | 5/6 (83%) [44%; 97%] | 17/28 (61%) [42%; 76%] | 25/26 (96%) [81%; 99%] | 8/31 (26%) [14%; 43%] | 12/42 (29%) [17%; 44%] | 1.1 / 2.54 | 1.0 |
| `nemo` | 3/6 (50%) [19%; 81%] | 13/28 (46%) [30%; 64%] | 26/26 (100%) [87%; 100%] | 12/31 (39%) [24%; 56%] | 19/42 (45%) [31%; 60%] | 5.62 / 6.55 | 1.0 |
| `guardrails_ai` | 4/6 (67%) [30%; 90%] | 22/28 (79%) [60%; 90%] | 24/26 (92%) [76%; 98%] | 28/31 (90%) [75%; 97%] | 33/42 (79%) [64%; 88%] | 97.18 / 200.65 | 15.92 |

## Fundamentação

| Candidato | Fiel aceita | Inventada barrada | Trocada barrada | Erros | Tempo p50 / p95 (s) |
|---|---|---|---|---:|---|
| `direto_pos` | 19/20 (95%) [76%; 99%] | 20/20 (100%) [84%; 100%] | 20/20 (100%) [84%; 100%] | 0 | 1.01 / 3.12 |
| `nemo` | 17/20 (85%) [64%; 95%] | 15/20 (75%) [53%; 89%] | 20/20 (100%) [84%; 100%] | 0 | 6.21 / 8.5 |
| `guardrails_ai` | 19/20 (95%) [76%; 99%] | 20/20 (100%) [84%; 100%] | 20/20 (100%) [84%; 100%] | 0 | 18.8 / 38.89 |

## Apoio: frases reais da amostra da #12 (rótulos do juiz automático do #68)

| Candidato | Concordância | Sustentada aceita | Não sustentada barrada | Kappa |
|---|---|---|---|---:|
| `direto_pos` | 44/60 (73%) [61%; 83%] | 21/21 (100%) [85%; 100%] | 23/39 (59%) [43%; 73%] | 0.5016 |
| `nemo` | 43/60 (72%) [59%; 81%] | 18/21 (86%) [65%; 95%] | 25/39 (64%) [48%; 77%] | 0.4444 |
| `guardrails_ai` | 42/60 (70%) [57%; 80%] | 17/21 (81%) [60%; 92%] | 25/39 (64%) [48%; 77%] | 0.4059 |
