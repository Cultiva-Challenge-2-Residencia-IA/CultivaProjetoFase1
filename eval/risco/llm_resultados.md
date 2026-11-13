# Camada semântica do detector de risco: resultados (issue #48)

Executado em 13/11/2026, num Apple M4 com 24 GB, Ollama local, temperatura 0. Critérios registrados antes em [`llm_criterios.md`](llm_criterios.md), com um adendo antes de ver o desempenho do LLM sozinho. Números completos em [`llm_resultados.json`](llm_resultados.json).

```bash
uv run python -m src.evaluation.risco_llm                              # desenvolvimento e perguntas comuns
uv run python -m src.evaluation.risco_llm --modelo qwen2.5:7b --holdout # medição única do holdout
```

## Desenvolvimento (`casos.json`: 110 positivos, 84 negativos difíceis) e perguntas comuns (151)

| Modelo | LLM sozinho: recall | LLM sozinho: precisão | Léxico + LLM: precisão | Perguntas comuns marcadas | p95 por chamada | Critérios |
|---|---:|---:|---:|---:|---:|---|
| `llama-guard3:1b` | 0,264 | 0,967 | 0,982 | 1/151 | 0,24 s | não (recall) |
| `llama-guard3:8b` | 0,473 | 0,963 | 0,974 | 2/151 | 0,90 s | não (recall) |
| **`qwen2.5:7b` + política** | **0,973** | 0,955 | 0,957 | **0/151** | 1,15 s | **sim** |

Recall do LLM sozinho por categoria (`qwen2.5:7b`): ideação 0,959, autolesão 1,000, comportamento alimentar 0,974.

Os Llama Guard 3 foram treinados para barrar **pedidos** de conteúdo nocivo, não para reconhecer alguém **dizendo** que está em crise; com a categoria S11, pegam pouco. O Qwen seguiu a política escrita a partir das definições do RF-IA03, **na primeira versão**, sem ajuste.

A primeira chamada de cada modelo carrega o modelo na memória (cerca de 2 s no 1b e 5 s no 8b). O consultor faz essa carga na inicialização, para a primeira pergunta caber no RNF29.

## Decisão

Pela regra registrada, o `qwen2.5:7b` é o único que cumpre os quatro critérios e passa a ser o padrão (`RISCO_LLM_MODELO`). Ele já é o modelo de geração do projeto (`OLLAMA_MODEL`), então o app mantém um só modelo na memória.

## Holdout (lote 3: 30 positivos, 25 negativos), medido uma vez

| | Só léxico | **Léxico + `qwen2.5:7b`** |
|---|---:|---:|
| Recall | 0,133 (4/30) | **0,733 (22/30)** |
| Ideação suicida | 1/12 | 10/12 |
| Autolesão | 2/7 | 6/7 |
| Comportamento alimentar | 1/11 | **6/11** |
| Falsos positivos | 0/25 | **0/25** |
| p95 por chamada | — | 1,21 s |

**O RF-IA03 continua não cumprido** (recall de 0,733, contra o mínimo de 0,95). O comportamento alimentar é o ponto mais fraco. Nada foi ajustado depois desta medição.

## Limitações

- **Viés de autoria:** o lote 3 e a política foram escritos pela mesma pessoa (MatheusSales2773, com Claude). A política não usa frases de nenhum conjunto, mas o 0,733 tende a ser otimista. A confirmação exige um lote novo, cego, escrito por outra pessoa sem ver a política.
- **Desenvolvimento x holdout:** 0,973 contra 0,733. As frases do desenvolvimento são, em geral, mais explícitas que as do lote 3.
- **CI:** não tem Ollama. O gate `risco_holdout:recall` continua medindo **só o léxico** (falha conhecida, piso 0,1333), e os testes usam um classificador simulado. O número do LLM vale para quem roda com o Ollama local.
- **Custo:** cerca de 1,2 s a mais em toda pergunta que o léxico não marca, inclusive nas comuns.
- **Uma máquina:** latência medida só no Apple M4; em computadores mais fracos, o p95 pode passar de 3 s, e aí o tempo limite (`RISCO_LLM_TIMEOUT`) faz valer só o léxico.
