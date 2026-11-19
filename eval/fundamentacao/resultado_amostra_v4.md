# Resultado da amostra de fundamentação v4 (RNF27, issue #67)

Registrado em 19/11/2026. Critérios na seção "Issue #67" de [`criterios.md`](criterios.md); julgamentos em [`amostra_v4_para_avaliar.csv`](amostra_v4_para_avaliar.csv).

## Como foi avaliado

- **Respostas:** 27 respostas do `qwen2.5:7b` com o prompt v4 (citação literal e mecanismo opcional), já sem as frases removidas, ou seja, o texto que chega ao usuário.
- **Amostra:** 59 frases (44 do `dev`, 15 do `test`), sorteadas como na amostra v3; havia só 59 frases elegíveis.
- **Juiz:**
  - o **ChatGPT**, com a mesma rubrica e o mesmo juiz da amostra v3, a pedido de MatheusSales2773;
  - é uma **estimativa por juiz automático**, sem avaliação humana independente;
  - foram enviados perguntas sintéticas e textos públicos do corpus, sem dados pessoais.

## Números

| | v3 (35%, PR #68) | **v4** |
|---|---:|---:|
| Sustentadas | 21/60 (35%) | **27/59 (46%)** |
| Parciais | 24 (40%) | 27 (46%) |
| Não sustentadas | 15 (25%) | **5 (8%)** |
| IC de Wilson de 95% da fidelidade | 24% a 48% | 34% a 58% |
| Frases do campo `physiological_mechanism` na amostra | 12 (17% sustentadas) | 0: o modelo passou a usar a frase fixa |

**Por campo:** `evidence_summary` 50% (17/34); `protocol_findings` 40% (10/25). **Por split:** `dev` 41% (18/44); `test` 60% (9/15).

**Medições do sistema** (`medicao_dev_prompt_v4b.log`, `medicao_test_prompt_v4b.log`):

| | `dev` | `test` |
|---|---:|---:|
| Respostas do LLM aceitas | 20/26 (77%) | 7/8 (87,5%) |
| Frases removidas | 4 | 2 |
| Rótulos corrigidos | 16 | 2 |
| Tempo mediano | 25 s | 39 s |

Também caíram na extrativa por passar dos 45 s: 1 resposta no `dev` e 4 no `test`.

## Leitura pela regra registrada antes de medir

A regra considerava a mudança **eficaz** com fidelidade de **55% ou mais** e limite inferior do IC acima de 35%. O resultado (**46%**, limite inferior de **34%**) **não atinge** a regra: a melhora de 11 p.p. não é distinguível do acaso com 59 frases. O RNF27 (95%) **continua não cumprido**.

## O que o resultado mostra

1. **A invenção caiu:** as frases não sustentadas passaram de 25% para 8%, e o campo de mecanismo, a pior fonte na v3, deixou de produzir afirmações. A exigência de citação literal faz o modelo se apoiar no texto entregue.
2. **O problema restante é o exagero.** Na maioria das frases parciais, a citação é verdadeira, mas a frase vai além dela:
   - generaliza a população do estudo (F004, F048);
   - transforma condição em regra (F051, F033);
   - tira o contexto, como uma orientação pós-bariátrica apresentada como geral (F030);
   - ou acrescenta exemplos e efeitos (F015, F039, F041).
3. **A checagem literal não pega isso**, nem citação real de um trecho sobre outro assunto (F031 e F050: trecho sobre dieta cetogênica citado em frase sobre fibras). As duas coisas exigem julgar o **sentido**, que é o tema do juiz de fundamentação da #52.
