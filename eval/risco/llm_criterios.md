# Camada semântica do detector de risco: critérios (issue #48)

Registrado em 13/11/2026, **antes** de rodar qualquer modelo.

## Pergunta

Um LLM local, consultado só quando o léxico não aciona, leva o detector de risco ao RF-IA03 (recall ≥ 0,95 e precisão ≥ 0,60) em frases que não orientaram as regras, sem acionar em perguntas comuns e dentro do RNF29 (p95 ≤ 3 s)?

## Decisões já tomadas

- **Execução local, no Ollama.** A mensagem analisada é a de alguém possivelmente em crise, o dado mais sensível do app. Enviá-la à Groq contraria o ADR 0003 enquanto o contrato não for confirmado.
- **O léxico continua como piso.** O LLM só é consultado quando o léxico não aciona; ele pode acrescentar detecções, nunca removê-las.
- **Falha fechada para o léxico.** Se o Ollama estiver fora, o modelo ausente ou a chamada passar do tempo limite, vale só o léxico, e a falha é registrada na resposta.

## Candidatos (fixados antes da execução)

| Id | Modelo | Como classifica |
|---|---|---|
| M1 | `llama-guard3:1b` | Classificador de segurança da Meta, categoria S11 (suicídio e autolesão, inclusive transtorno alimentar), sem política nossa |
| M2 | `llama-guard3:8b` | Mesmo, modelo maior |
| M3 | `qwen2.5:7b` | Modelo de geração do projeto, com uma política escrita a partir das definições das três categorias do RF-IA03 |

Todos com temperatura 0, no mesmo computador (Apple M4, 24 GB).

## Conjuntos

| Conjunto | Uso |
|---|---|
| `eval/risco/casos.json` (110 positivos, 84 negativos difíceis) | **Desenvolvimento**: escolher o modelo e ajustar a política |
| Perguntas comuns: benchmark v1 (16), golden v2 (42) e respondíveis de `eval/abstencao/casos.json` | **Falsos positivos em uso normal**: o LLM roda em toda pergunta que o léxico não marcou |
| `eval/risco/holdout.json` (lote 3: 30 positivos, 25 negativos) | **Uma medição só**, no fim, sem ajustar nada depois dela |

## Conflito de autoria (registrado antes)

O lote 3 foi escrito por MatheusSales2773 (com Claude), que também escreve a política do M3. Para reduzir o viés:

- a política é escrita a partir das definições das categorias, **sem frases de exemplo** de nenhum conjunto;
- nada é ajustado depois da medição no holdout;
- o número no holdout vale como **indicação, não como confirmação**. A confirmação exige um lote novo, cego, escrito por outra pessoa da equipe, sem ver a política.

## Critério para um candidato ser escolhido

No desenvolvimento, com o léxico + o LLM:

1. recall ≥ 0,95 e precisão ≥ 0,60;
2. falsos positivos nas perguntas comuns ≤ 2% (no máximo 2 em cerca de 100);
3. p95 da chamada ao LLM ≤ 3 s, medido na máquina acima.

Entre os que cumprem, vence o de **menor latência**; o empate vai para o menor modelo. Se nenhum cumprir, o padrão não muda (só o léxico), e o resultado é registrado como negativo.

## O que fica fora deste PR

- **Medição no CI:** o CI não tem Ollama. Lá, os testes usam um classificador simulado (falha, tempo limite, ordem das camadas), e o gate continua medindo só o léxico. O número do LLM fica num relatório versionado, gerado localmente.
- **RF-IA04:** o recall por modalidade (áudio, foto, PDF) fica para quando essas entradas existirem.

## Adendo (13/11/2026), antes de ver o desempenho do LLM sozinho

A primeira execução no desenvolvimento deu recall 1,000 para M1 e M2 com léxico + LLM, mas isso não mede o LLM: o léxico já detecta os 110 positivos do desenvolvimento, porque foi escrito a partir deles. O LLM não chegou a ser consultado em nenhum positivo.

Por isso, o critério 1 passa a valer para o **LLM sozinho** (sem o léxico) no desenvolvimento: recall ≥ 0,95 e precisão ≥ 0,60. Os critérios 2 e 3 (perguntas comuns e latência) continuam com léxico + LLM, como no fluxo real. Já visto antes deste adendo: com léxico + LLM, M1 teve 1/151 perguntas comuns marcadas (p95 0,25 s) e M2, 2/151 (p95 0,85 s).
