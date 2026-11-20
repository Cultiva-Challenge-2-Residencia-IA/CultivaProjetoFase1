# Resultado da amostra de fundamentação v5 com o `gemma4:e4b` (RNF27)

Registrado em 20/11/2026. Julgamentos em [`amostra_v5_gemma4_para_avaliar.csv`](amostra_v5_gemma4_para_avaliar.csv), rubrica em [`rubrica.md`](rubrica.md), prompt do juiz em [`prompt_juiz.md`](prompt_juiz.md).

## Como foi avaliado (leia antes dos números)

- **O que mudou em relação à v4 do `gemma4:e4b`:** só o prompt. A v5 acrescenta a regra 7 em `src/agent/llm_client.py`: a frase mantém a condição, o público, a força e o alcance do trecho, e cada número fica ligado ao que mede. Modelo, opções do Ollama e semente do sorteio (12) são os mesmos.
- **Origem da regra:** ela foi escrita a partir das 10 parciais da amostra v4 do `gemma4:e4b`, das quais 3 eram do `test` (F011, F047 e F057). O `test` deixou de ser uma medida independente para a v5. Os exemplos da regra são genéricos, não as frases julgadas.
- **Amostra:** 60 frases de 31 respostas (42 do `dev` e 18 do `test`), sorteadas entre as frases que passaram nas checagens de citação. Por campo: 41 de `evidence_summary` e 19 de `protocol_findings`.
- **Juiz:** ChatGPT, em conversa nova, com a planilha, a `rubrica.md` e o texto de `prompt_juiz.md`. Modelo e modo do juiz a confirmar pelo autor. **Não houve avaliação humana independente**: o número é uma estimativa por juiz automático, não a medição que o RNF27 pede.
- **Uma rodada por pergunta.** O LLM não é determinístico entre execuções, e as amostras v4 e v5 têm frases diferentes; a diferença entre elas inclui essa variação.

## Números

| | v4, `gemma4:e4b` | **v5, `gemma4:e4b`** |
|---|---:|---:|
| Sustentadas | 83% (50/60) | **85% (51/60)** |
| Parciais | 17% (10) | 15% (9) |
| Não sustentadas | 0% | 0% |
| IC de Wilson de 95% | 72% a 91% | **74% a 92%** |
| Meta do RNF27 | 95% (não atingida) | 95% (não atingida) |

**Por campo:** `evidence_summary` 85% (35/41) e `protocol_findings` 84% (16/19). **Por split:** `dev` 83% (35/42) e `test` 89% (16/18).

**Forma da citação na mesma rodada** (`medicao_*_prompt_v5_gemma4.log`):

| | v4 dev / test | v5 dev / test |
|---|---:|---:|
| Respostas do LLM aceitas | 89% / 92% | 85% (22/26) / 83% (10/12) |
| Frases que chegam ao usuário | 106 / 61 | 97 / 51 |
| Frases removidas por citação inexistente | 11 / 4 | 10 / 6 |
| Tempo mediano | 10,5 s / 13 s | 9,9 s / 10,3 s |

No `dev`, as 4 respostas recusadas com a v5 são todas de perguntas com grafo ou TACO (V2-GRA-01, V2-GRA-02, V2-TAC-01 e V2-TAC-02): o modelo citou só `[GRAFO]` ou `[TACO]`, e o verificador exige ao menos um `[T#]`. Na v4, duas delas (GRA-01 e TAC-01) passaram. Em V2-TAC-01, a resposta pela TACO estava certa e foi trocada pela síntese extrativa.

## O que o resultado mostra

1. **A v5 não melhorou a fidelidade de forma mensurável.** 85% contra 83%, com intervalos quase iguais; a diferença cabe na variação da amostra.
2. **As parciais continuam com os mesmos padrões:**
   - **condição ou população perdida:** estudo com mulheres generalizado para "indivíduos" (F003), faixa de carboidratos de dietas cetogênicas estudadas na obesidade apresentada como regra geral (F012), "barreiras adicionais" sem o "adicionais" (F024), exceção omitida (F025), efeito da vitamina C sem a dose de 75 mg (F042), distribuição de macronutrientes atribuída a todas as participantes (F053);
   - **recomendação mais categórica que a fonte:** condição virou orientação (F017), "nunca usar" estendido à maioria (F047);
   - **atribuição:** diretriz atribuída à SBME sem que o trecho diga isso (F030).
3. **Custo:** menos respostas aceitas e menos frases por resposta, sobretudo nas perguntas com grafo ou TACO.

## Conclusão

A regra no prompt não resolve as parciais com o `gemma4:e4b`: ele lê a regra, mas continua perdendo a condição da fonte em cerca de 15% das frases. A v5 não deve virar padrão com base nesta amostra, porque não mostrou ganho e reduziu a conformidade. Próximos passos possíveis:

- uma checagem depois da geração, que compare cada frase com a citação e remova ou reescreva a que vai além dela (a chamada direta ao LLM da #52 é candidata);
- julgar de novo a amostra v4 do `qwen2.5:7b` com `prompt_juiz.md`, ainda pendente: o arquivo devolvido em 20/11 era idêntico ao original, com os julgamentos antigos, e não conta como novo julgamento;
- uma amostra julgada por um colega, que é o que o RNF27 pede.
