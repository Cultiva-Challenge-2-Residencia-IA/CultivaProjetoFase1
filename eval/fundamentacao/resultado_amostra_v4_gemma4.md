# Resultado da amostra de fundamentação v4 com o `gemma4:e4b` (RNF27)

Registrado em 20/11/2026. Julgamentos em [`amostra_v4_gemma4_para_avaliar.csv`](amostra_v4_gemma4_para_avaliar.csv), rubrica em [`rubrica.md`](rubrica.md), prompt do juiz em [`prompt_juiz.md`](prompt_juiz.md).

## Como foi avaliado (leia antes dos números)

- **O que mudou em relação à v4 do qwen:** só o modelo. O prompt é o v4 da #67 (citação literal e mecanismo opcional), e a semente do sorteio é a mesma (12).
- **Modelo:** `gemma4:e4b`, padrão desde o ADR 0004. Rodou sozinho, com `OLLAMA_FALLBACK_MODEL` vazio, no Ollama 0.40.16, numa AMD Radeon RX 9060 XT com o modelo 100% na GPU.
- **Amostra:** 60 frases de 32 respostas (45 do `dev` e 15 do `test`), sorteadas entre as frases que passaram nas checagens de citação. Por campo: 43 de `evidence_summary`, 16 de `protocol_findings` e 1 de `physiological_mechanism`.
- **Juiz:**
  - ChatGPT 6.2 Astra, no modo Ultra (segundo o autor), em conversa nova, com a planilha, a `rubrica.md` e o texto de `prompt_juiz.md`;
  - **não houve avaliação humana independente**, então o número é uma estimativa por juiz automático, não a medição que o RNF27 pede.
- **Efeito do modelo isolado (adendo de 20/11/2026).** A amostra v4 do qwen foi julgada de novo, em conversa nova, pelo mesmo juiz, com a planilha sem julgamentos e o texto de `prompt_juiz.md` ([`amostra_v4_rejulgada.csv`](amostra_v4_rejulgada.csv)). Os comentários são novos, e os 59 julgamentos coincidem com os originais: 46% (27/59). A diferença entre 46% e 83% vem do modelo, não do pedido ao juiz. Ressalva: a concordância total pode refletir memória do ChatGPT entre conversas, que não foi verificada.
- **Conferência pontual:** conferi 8 frases sustentadas, sorteadas com semente 7 (F004, F005, F008, F012, F025, F031, F041 e F051). Nas 8, o trecho citado diz o que a frase afirma; a maioria das frases reproduz o trecho quase palavra por palavra. As outras 52 não foram conferidas por pessoa.

## Números

| | v3, `qwen2.5:7b` | v4, `qwen2.5:7b` | **v4, `gemma4:e4b`** |
|---|---:|---:|---:|
| Sustentadas | 35% (21/60) | 46% (27/59) | **83% (50/60)** |
| Parciais | 40% | 46% | 17% |
| Não sustentadas | 25% | 8% | **0%** |
| IC de Wilson de 95% | 24% a 48% | 34% a 58% | **72% a 91%** |
| Meta do RNF27 | 95% | 95% | 95% (não atingida) |

**Por campo:** `evidence_summary` 86% (37/43), `protocol_findings` 75% (12/16) e `physiological_mechanism` 1/1.

**Por split:** `dev` 84% (38/45) e `test` 80% (12/15).

**Forma da citação na mesma rodada** (`medicao_*_prompt_v4_gemma4.log`):

| | `qwen2.5:7b` dev / test | `gemma4:e4b` dev / test |
|---|---:|---:|
| Respostas do LLM aceitas | 77% / 87,5% | 89% / 92% |
| Frases que chegam ao usuário | 47 / 15 | 106 / 61 |
| Frases removidas por citação inexistente | 4 / 2 | 11 / 4 |
| Tempo mediano | 25 s / 39 s | 10,5 s / 13 s |

## O que o resultado mostra

1. **Nenhuma frase inventada na amostra.** As 10 falhas são todas parciais: a citação existe, mas a frase vai além dela.
2. **O `gemma4:e4b` escreve perto do texto da fonte.** Isso explica boa parte do ganho, mas tem um custo: algumas frases são cópias quase literais e uma termina cortada (F004, "tendendo a desfavorecer"). A pertinência da frase para a pergunta não é medida aqui.
3. **As parciais seguem dois padrões:**
   - **condição ou população perdida:** suplementação pós-bariátrica apresentada como geral (F042), creatina para vegetarianos e idosos sem o critério de avaliação especializada (F047), fadiga só em exercícios intermitentes (F036), números atribuídos às barreiras erradas (F006), conclusão sobre suplementos estendida à planta em geral (F020), orientação do grupo controle (F045), exceções omitidas (F057);
   - **recomendação mais categórica que a fonte:** "deve" no lugar de "evite ou minimize" (F011), efeito apresentado como certo quando "alguns estudos" o indicam (F023), benefício transformado em prescrição (F030).

## Conclusão

Com o `gemma4:e4b` e o prompt v4, a estimativa de fidelidade sobe de 46% para 83%, ainda abaixo da meta de 95%. Com o qwen julgado de novo pelo mesmo pedido (46%), o ganho é atribuível ao modelo. Próximos passos:

- prompt v5 contra os dois padrões das parciais: manter condição, população e dose da fonte, e não tornar a recomendação mais forte que a fonte;
- uma amostra julgada por um colega, que é o que o RNF27 pede.
