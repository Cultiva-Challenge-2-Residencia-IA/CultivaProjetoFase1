# Conjuntos do detector de risco (RF-IA03)

| Arquivo | Para que serve | Quem escreve |
|---|---|---|
| `casos.json` | **Desenvolvimento.** Orienta o léxico (`src/guardrails/risco/lexico.yaml`). Cada caso traz a `origem` (lote 1: autor do léxico; lote 2: revisão às cegas do PR #41). | Quem mantém o detector |
| `holdout.json` | **Validação.** Mede se o detector generaliza para frases que não orientaram as regras. | Outra pessoa, sem olhar o léxico |

O benchmark grava as duas medidas no relatório (`risk_metrics` e `risk_metrics_holdout`), e o gate exige recall ≥ 0,95 nas duas (`eval/gates.toml`). A precisão (≥ 0,60) é cobrada só no desenvolvimento, que tem negativos suficientes.

## Regras

- **Léxico e holdout mudam em PRs de pessoas diferentes.** Quem altera o léxico ou os exemplos não acrescenta casos ao holdout no mesmo PR. Assim o holdout continua medindo generalização, e não cobertura.
- **Holdout que orientou regras deixa de ser cego.** Quando uma frase do holdout for usada para escrever uma regra, mova-a para `casos.json` e registre isso. As 19 frases atuais vieram da revisão do PR #41 e orientaram a ampliação pedida nela, por isso `autoria.cego` está `false`. O próximo passo é um lote novo, escrito sem olhar o léxico.
- **Erre para o lado de acionar.** Uma pessoa em crise que não recebe a mensagem de acolhimento é o erro grave. Um falso positivo custa uma resposta de nutrição trocada pela mensagem com o CVV 188.

## Histórico

- 10/11/2026: o léxico original acertava 60 de 60 frases do próprio autor, mas 0 de 19 frases da revisão do PR #41. Isso motivou a separação entre os dois conjuntos.
- 10/11/2026: entrou uma camada de similaridade por embeddings (`paraphrase-multilingual-MiniLM-L12-v2`).
- 12/11/2026: um segundo lote, às cegas, teve recall de 0,667 (comportamento alimentar: 3 de 10), e a similaridade acionou em 4 de 20 perguntas comuns. O lote foi para o desenvolvimento, e o léxico ganhou regras com número (jejum, calorias, quantidade de remédios), intenção com método, comportamentos compensatórios e exceções de expressões comuns.
- 12/11/2026: camadas semânticas avaliadas e **descartadas**:
  - **similaridade por embeddings:** com o léxico novo, não acrescentava nenhum risco detectado e gerava 4 alarmes falsos no lote 2;
  - **NLI zero-shot multilíngue** (`mDeBERTa-v3-base-xnli`): na melhor hipótese pegava cerca de metade dos riscos; a de comportamento alimentar acionava em 17 de 54 perguntas comuns; custava cerca de 1 s por mensagem e mais de 1 GB de dependências.
- Próximo passo para paráfrases que nenhuma regra prevê: um LLM classificador de segurança (por exemplo, `openai/gpt-oss-safeguard-20b`), com o léxico como piso.
