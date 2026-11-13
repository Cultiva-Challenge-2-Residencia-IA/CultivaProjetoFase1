# Conjuntos do detector de risco (RF-IA03)

| Arquivo | Para que serve | Quem escreve |
|---|---|---|
| `casos.json` | **Desenvolvimento.** Orienta o léxico (`src/guardrails/risco/lexico.yaml`). Cada caso traz a `origem` (lote 1: autor do léxico; lote 2: revisão às cegas do PR #41; `holdout-revisao1-pr41-matheus`: o holdout antigo, que deixou de ser cego). | Quem mantém o detector |
| `holdout.json` | **Validação.** Mede se o detector generaliza para frases que não orientaram as regras. | Outra pessoa, sem olhar o léxico |

O benchmark grava as duas medidas no relatório (`risk_metrics` e `risk_metrics_holdout`), e o gate exige recall ≥ 0,95 nas duas (`eval/gates.toml`). A precisão (≥ 0,60) é cobrada só no desenvolvimento.

> **Atenção:** O RF-IA03 **não está cumprido.** No holdout atual (lote 3, cego), o recall do léxico é **0,133** (4 de 30), sem falsos positivos nas 25 perguntas comuns. O gate `risco_holdout:recall` aparece como **falha conhecida** (`falha_conhecida` e `piso_conhecido` em `eval/gates.toml`): aviso com o número real, sem falhar o job, e falha de verdade se o recall cair abaixo de 0,1333, e o teste `test_holdout_de_risco_atende_o_rf_ia03` está marcado como `xfail` estrito até a issue #48. O teste de falsos positivos no holdout continua obrigatório.

## Regras

- **Léxico e holdout mudam em PRs de pessoas diferentes.** Quem altera o léxico ou os exemplos não acrescenta casos ao holdout no mesmo PR. Assim o holdout continua medindo generalização, e não cobertura.
- **Holdout que orientou regras deixa de ser cego.** Quando uma frase do holdout for usada para escrever uma regra, mova-a para `casos.json` e registre isso. Foi o caso das 19 frases da primeira revisão do PR #41, movidas para `casos.json` em 12/11/2026. O holdout atual é o lote 3 (`autoria.cego: true`). **Não amplie o léxico a partir dele**: a próxima melhoria do detector vem da issue #48.
- **Erre para o lado de acionar.** Uma pessoa em crise que não recebe a mensagem de acolhimento é o erro grave. Um falso positivo custa uma resposta de nutrição trocada pela mensagem com o CVV 188.

## Histórico

- 10/11/2026: o léxico original acertava 60 de 60 frases do próprio autor, mas 0 de 19 frases da revisão do PR #41. Isso motivou a separação entre os dois conjuntos.
- 10/11/2026: entrou uma camada de similaridade por embeddings (`paraphrase-multilingual-MiniLM-L12-v2`).
- 12/11/2026: um segundo lote, às cegas, teve recall de 0,667 (comportamento alimentar: 3 de 10), e a similaridade acionou em 4 de 20 perguntas comuns. O lote foi para o desenvolvimento, e o léxico ganhou regras com número (jejum, calorias, quantidade de remédios), intenção com método, comportamentos compensatórios e exceções de expressões comuns.
- 12/11/2026: camadas semânticas avaliadas e **descartadas**:
  - **similaridade por embeddings:** com o léxico novo, não acrescentava nenhum risco detectado e gerava 4 alarmes falsos no lote 2;
  - **NLI zero-shot multilíngue** (`mDeBERTa-v3-base-xnli`): na melhor hipótese pegava cerca de metade dos riscos; a de comportamento alimentar acionava em 17 de 54 perguntas comuns; custava cerca de 1 s por mensagem e mais de 1 GB de dependências.
- Próximo passo para paráfrases que nenhuma regra prevê: um LLM classificador de segurança (por exemplo, `openai/gpt-oss-safeguard-20b`), com o léxico como piso (issue #48).
- 12/11/2026: lote 3, escrito às cegas por MatheusSales2773 antes de ler o léxico estruturado, virou o holdout (30 positivos e 25 negativos). Recall de **0,133** (ideação 1/12, autolesão 2/7, comportamento alimentar 1/11) e nenhum falso positivo. O padrão das três rodadas é o mesmo: 100% no que orientou as regras e pouco em frases novas.
- 13/11/2026 (issue #48): camada semântica com LLM **local** (Ollama), consultada só quando o léxico não aciona. Dos três candidatos, só o `qwen2.5:7b` com uma política escrita a partir das definições do RF-IA03 cumpriu os critérios no desenvolvimento (LLM sozinho: recall 0,973, precisão 0,955; 0 de 151 perguntas comuns; p95 1,15 s); os Llama Guard 3 ficaram em 0,26 e 0,47. No holdout, medido uma vez, léxico + LLM: recall **0,733** e nenhum falso positivo. O RF-IA03 segue não cumprido, e o número tende a ser otimista porque o lote 3 e a política têm o mesmo autor. Detalhes em [`llm_resultados.md`](llm_resultados.md). O gate do CI continua medindo só o léxico, porque o CI não tem Ollama.
