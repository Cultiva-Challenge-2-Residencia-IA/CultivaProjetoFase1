# Comparação de modelos locais (issue #55)

Gerado por `uv run python -m src.evaluation.modelo_local relatorio`. Não edite à mão. Como ler: [`resultados_explicados.md`](resultados_explicados.md).

Casos: 96 · sementes: [1, 2, 3] · condições: `{"temperatura": 0.1, "num_ctx": 8192, "num_predict": 1024, "think": false, "juiz": "claude-sonnet (subagente, às cegas)"}`

| Modelo | Passa | JSON e esquema | Prescrição (seg.) | Fidelidade (todas / semente 1) | Cobertura de termos | ROUGE-L prec. | BERTScore prec. | p50 (s) | p95 (s) | tok/s | VRAM (GB) | Ferramentas: escolha / args |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `qwen2.5:7b` | sim | 99.7% | 5 em 30 (10 julgadas) | 71.0% / 71.0% (n=40) | 77.1% | 40.8% | 68.8% | 6.03 | 9.00 | 78.74 | 5.1 | 93.8% / 91.7% |
| `qwen3.5:9b` | sim | 100.0% | 1 em 30 (30 julgadas) | 72.7% / 71.2% (n=120) | 82.0% | 35.4% | 68.2% | 7.93 | 12.69 | 65.96 | 5.7 | 87.5% / 83.3% |
| `gemma4:e4b` | sim | 100.0% | 1 em 30 (30 julgadas) | 93.5% / 94.1% (n=120) | 81.4% | 43.3% | 71.0% | 3.23 | 5.16 | 161.48 | n/d | 89.6% / 86.1% |
| `llama3.1:8b` | sim | 100.0% | 0 em 30 (10 julgadas) | 69.1% / 69.1% (n=40) | 76.4% | 52.1% | 70.7% | 5.24 | 8.19 | 75.61 | 5.8 | 89.6% / 100.0% |
| `mistral-nemo:12b` | sim | 100.0% | 1 em 30 (10 julgadas) | 67.9% / 67.9% (n=40) | 75.4% | 45.7% | 71.5% | 22.21 | 34.30 | 16.43 | 6.7 de 8.6 | 75.0% / 66.7% |

## Diferença para a referência (`qwen2.5:7b`), bootstrap pareado

| Modelo | Fidelidade: dif. [IC 95%] | Cobertura: dif. [IC 95%] |
|---|---|---|
| `qwen3.5:9b` | +1.7 p.p. [-3.8; +7.4] (empate) | +4.8 p.p. [-1.2; +11.5] (empate) |
| `gemma4:e4b` | +22.6 p.p. [+17.6; +27.7] * | +4.1 p.p. [-1.7; +10.9] (empate) |
| `llama3.1:8b` | -1.9 p.p. [-10.0; +5.4] (empate) | -0.9 p.p. [-6.2; +5.6] (empate) |
| `mistral-nemo:12b` | -3.1 p.p. [-11.3; +5.2] (empate) | -1.9 p.p. [-8.7; +5.4] (empate) |

`*` = intervalo sem o zero. Sem asterisco, a diferença é empate técnico.

## Classificação

Ordem: `gemma4:e4b`, `qwen3.5:9b`, `qwen2.5:7b`, `llama3.1:8b`, `mistral-nemo:12b`. Empatados com o líder (desempate por latência e VRAM): `gemma4:e4b`.

Finalistas (principal e reserva): `gemma4:e4b`, `qwen3.5:9b`.
- fidelidade, 1º menos 2º: +20.8 p.p. [+16.9; +24.8] *
- cobertura_termos, 1º menos 2º: -0.7 p.p. [-7.6; +6.5] (empate)
