# Conjuntos do detector de risco (RF-IA03)

| Arquivo | Para que serve | Quem escreve |
|---|---|---|
| `casos.json` | **Desenvolvimento.** Orienta o léxico (`src/guardrails/risco/lexico.yaml`) e os exemplos da camada de similaridade (`exemplos.yaml`). | Quem mantém o detector |
| `holdout.json` | **Validação.** Mede se o detector generaliza para frases que não orientaram as regras. | Outra pessoa, sem olhar o léxico |

O benchmark grava as duas medidas no relatório (`risk_metrics` e `risk_metrics_holdout`), e o gate exige recall ≥ 0,95 nas duas (`eval/gates.toml`). A precisão (≥ 0,60) é cobrada só no desenvolvimento, que tem negativos suficientes.

## Regras

- **Léxico e holdout mudam em PRs de pessoas diferentes.** Quem altera o léxico ou os exemplos não acrescenta casos ao holdout no mesmo PR. Assim o holdout continua medindo generalização, e não cobertura.
- **Holdout que orientou regras deixa de ser cego.** Quando uma frase do holdout for usada para escrever uma regra, mova-a para `casos.json` e registre isso. As 19 frases atuais vieram da revisão do PR #41 e orientaram a ampliação pedida nela, por isso `autoria.cego` está `false`. O próximo passo é um lote novo, escrito sem olhar o léxico.
- **Erre para o lado de acionar.** Uma pessoa em crise que não recebe a mensagem de acolhimento é o erro grave. Um falso positivo custa uma resposta de nutrição trocada pela mensagem com o CVV 188.

## Histórico

- 10/11/2026: o léxico original acertava 60 de 60 frases do próprio autor, mas 0 de 19 frases da revisão do PR #41. Isso motivou a separação entre os dois conjuntos e a camada de similaridade.
