# Resultado da amostra de fundamentação (RNF27, issue #12)

Registrado em 19/11/2026. Critérios em [`criterios.md`](criterios.md), rubrica em [`rubrica.md`](rubrica.md), julgamentos em [`amostra_para_avaliar.csv`](amostra_para_avaliar.csv).

## Como foi avaliado (leia antes dos números)

- **Amostra:** 60 frases de 28 respostas do `qwen2.5:7b` com o prompt v3 (42 do `dev`, 18 do `test`), sorteadas com semente fixa entre as respostas que passaram na checagem de citações. O `qwen2.5:7b` era o modelo padrão na época; desde o ADR 0004 o padrão é o `gemma4:e4b`, e o `qwen2.5:7b` é a reserva. A amostra não foi refeita com o `gemma4:e4b`.
- **Avaliador:**
  - os julgamentos foram produzidos com um **LLM externo, o ChatGPT**, a pedido de MatheusSales2773, que é autor do PR #61;
  - **não houve avaliação humana independente**, que é o que o RNF27 e os critérios pedem;
  - o resultado é, portanto, uma **estimativa por juiz automático**, não a medição humana do requisito.
- **Envio a serviço externo:** a planilha tem perguntas sintéticas do benchmark e textos públicos do corpus, sem dados pessoais (ADR 0003).
- **Conferência pontual:** nas frases F023, F031 e F037, marcadas como não sustentadas, as palavras-chave da afirmação (potássio e natriurese; piperina, curcumina e "20 vezes") **não aparecem** no trecho citado, o que confirma o julgamento nesses casos. As outras 57 não foram conferidas por pessoa.

## Números

| | |
|---|---:|
| Sustentadas | 21 de 60 |
| Parciais (contam como não sustentadas) | 24 |
| Não sustentadas | 15 |
| **Fidelidade** | **35%** (IC de Wilson de 95%: 24% a 48%) |
| Meta do RNF27 | 95% |

**Por campo da resposta:**

| Campo | Frases | Sustentadas | Parciais | Não sustentadas |
|---|---:|---:|---:|---:|
| `evidence_summary` | 31 | 15 (48%) | 14 | 2 |
| `protocol_findings` | 17 | 4 (24%) | 8 | 5 |
| `physiological_mechanism` | 12 | 2 (17%) | 2 | 8 |

**Por split:** `dev` 29% (12/42) e `test` 50% (9/18).

## O que o resultado mostra

1. **A checagem determinística confere a forma, não a fundamentação.** O prompt v3 elevou a conformidade de citação de 15% para cerca de 90%, mas boa parte das citações é decorativa: o modelo põe um `[T#]` em afirmações que vêm do próprio conhecimento.
2. **O campo `physiological_mechanism` é a principal fonte de afirmações sem base.**
   - **Por que acontece:** o esquema da resposta exige um mecanismo, e os Trechos raramente descrevem mecanismo, então o modelo o escreve por conta própria e cita um Trecho qualquer.
   - **Exemplos:** piperina e curcumina "até 20 vezes" citando um trecho sobre carboidratos (F031); potássio e natriurese citando um trecho sobre comer com atenção (F023).
3. **As "parciais" são, na maioria, exageros:**
   - a frase tira a condição ou a ressalva da fonte (F009, F016, F043);
   - transforma faixa em valor único ou omite a dose (F027);
   - ou acrescenta exemplos que não estão no trecho (F001, F028).

## Conclusão

O RNF27 **não está cumprido** pela estimativa disponível (35% contra a meta de 95%), e a medição humana independente que o requisito pede não foi feita. A melhoria fica na #67 (citação literal verificável e mecanismo opcional). Alguns caminhos:

- tirar ou tornar opcional o campo de mecanismo;
- exigir que cada frase traga um trecho literal da fonte;
- um juiz de fundamentação que bloqueie frases sem sustentação (#52).
