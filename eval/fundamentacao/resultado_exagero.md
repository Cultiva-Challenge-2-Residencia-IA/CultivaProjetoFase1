# Resultado da checagem de exagero (issue #86)

Registrado em 21/11/2026. Critérios definidos antes da medição em [`exagero_criterios.md`](exagero_criterios.md), commitados antes de o verificador rodar em qualquer frase. Código em `src/evaluation/exagero.py`.

## Conclusão

**A checagem não foi ligada no produto.** Foram testados dois verificadores, e nenhum passou no critério: o próprio `gemma4:e4b` e, separado do modelo principal, um modelo pequeno de NLI no processador (seção "Segunda tentativa"). Com o `gemma4:e4b`, a versão final do verificador não achou nenhuma das 5 parciais do `test`. O critério pedia pelo menos 50% de parciais achadas, com no máximo 10% de frases sustentadas removidas. No `dev`, onde ele foi ajustado, achou 36%.

A hipótese da issue era que uma segunda chamada ao mesmo modelo acharia a maioria das parciais. Os dados não a sustentam: o modelo que perde a condição ao escrever também não a vê ao conferir.

## Como foi medido

- **Frases:** as 120 frases já julgadas pelo ChatGPT nas amostras v4 e v5 do `gemma4:e4b`. São 87 do `dev` (73 sustentadas e 14 parciais) e 33 do `test` (28 sustentadas e 5 parciais).
- **Verificador:** uma chamada por frase ao `gemma4:e4b` local, com temperatura 0 e semente fixa. A chamada recebe a frase sem os marcadores e o texto dos Trechos que ela cita.
- **Decisão:** como houve ajuste no `dev`, a decisão usa só o `test`, rodado uma única vez com a versão final (regra 2 dos critérios).
- **Juiz:** o julgamento de referência é o do ChatGPT, não uma avaliação humana.

## Versões

| Versão | O que muda | Parciais achadas (`dev`) | Sustentadas removidas (`dev`) | Taxa projetada (`dev`) | Tempo mediano por frase |
|---|---|---:|---:|---:|---:|
| v1 | Pergunta direta, com as quatro categorias de exagero e exemplos genéricos | 2/14 (14%) | 1/73 (1%) | 85,7% (antes: 83,9%) | 2,4 s |
| **v2 (final)** | Lista primeiro as ressalvas do trecho, depois as perdidas, e só então dá o veredito | 5/14 (36%) | 4/73 (5%) | 88,5% | 3,3 s |
| v3 | Prompt da v2 com o raciocínio do modelo ligado (`think`) | 3/3 nas 13 primeiras frases | 6/10 nas 13 primeiras | — | mais de 45 s |

**v3 interrompida:** em mais de 10 minutos, julgou só 13 frases ([`exagero_exagero-v3_dev_interrompida.log`](exagero_exagero-v3_dev_interrompida.log)). Uma resposta tem cerca de 5 frases, então a checagem somaria minutos a cada resposta. Nas 13 frases que julgou, ela também removeu 6 de 10 sustentadas. Foi abandonada por tempo antes de completar o `dev`.

**Prompt da v1** (a v2 está no código):

> Você confere se uma FRASE de uma resposta de Nutrição é sustentada pelos TRECHOS que ela cita. A FRASE é sustentada só se os TRECHOS afirmam tudo o que ela afirma, diretamente ou por paráfrase fiel. A FRASE NÃO é sustentada quando: 1. perde uma condição, um público, uma dose, uma quantidade, uma duração ou o contexto que os TRECHOS ligam à afirmação (exemplos genéricos: gestantes viram "pessoas"; efeito com 2 g por dia sem a dose; resultado de um estudo como regra geral); 2. é mais forte que os TRECHOS ("pode", "sugere" viram "deve", "sempre"; descrição vira recomendação); 3. atribui a afirmação a órgão, autor, diretriz ou estudo que os TRECHOS não indicam; 4. acrescenta número, efeito, mecanismo, exemplo ou conclusão. Resumo sem perder condição, sinônimos e omissão de detalhes que não mudam o sentido continuam sustentados. Responda só com JSON: `{"sustentada": true | false, "problema": "..."}`

## Resultado no `test` (v2, decisão)

| | Resultado | Critério |
|---|---:|---:|
| Parciais achadas | **0/5 (0%)** | ≥ 50% |
| Sustentadas removidas | 0/28 (0%) | ≤ 10% |
| Taxa projetada | 84,8% (igual à de antes) | |
| Falhas | 0 | |
| Tempo mediano por frase | 3,1 s | |

As 5 parciais do `test`, todas mantidas pelo verificador, com o motivo do juiz:

- **v4-F011:** o Guia aconselha evitar ou minimizar o açúcar; a frase diz "deve".
- **v4-F047:** a fonte admite a creatina após avaliação especializada; a frase cita vegetarianos e idosos sem esse critério.
- **v4-F057 e v5-F047:** a passagem admite raras exceções; a frase vira regra para "a maioria".
- **v5-F030:** a diretriz é atribuída à SBME sem que o trecho diga isso.

Arquivos: [`exagero_exagero-v1_dev.json`](exagero_exagero-v1_dev.json), [`exagero_exagero-v2_dev.json`](exagero_exagero-v2_dev.json), [`exagero_exagero-v2_test.json`](exagero_exagero-v2_test.json).

## Segunda tentativa: modelo de NLI, separado do principal

O modelo principal não deve mudar, e um segundo LLM do mesmo porte não cabe junto na GPU de 8 GB. Por isso a segunda tentativa usou um modelo pequeno de inferência textual (NLI), que roda no processador: o `MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7`, fixado no adendo dos critérios antes de rodar.

- **Como funciona:** a frase recebe a maior probabilidade de "o Trecho garante a frase" (`entailment`) entre os Trechos citados. O limiar foi escolhido no `dev` (0,0717, o maior com remoção indevida de até 10%) e congelado. Depois o `test` rodou uma vez.
- **Ressalva:** o `test` já tinha sido usado na rodada do `gemma4:e4b`.

| Conjunto | Parciais achadas | Sustentadas removidas | Taxa projetada | Tempo mediano por frase |
|---|---:|---:|---:|---:|
| `dev` | 2/14 (14%) | 7/73 (10%) | 84,6% (antes: 83,9%) | 3,6 s |
| **`test`** | **1/5 (20%)** | 2/28 (7%) | 86,7% (antes: 84,8%) | 3,1 s |

**Não passou no critério** (≥ 50% de parciais achadas). O motivo aparece nas pontuações do `dev`: a mediana é 0,971 nas sustentadas e 0,966 nas parciais. O modelo vê as duas como igualmente garantidas pelo Trecho. Isso é esperado: a parcial repete as palavras do Trecho e só perde uma condição, e o NLI premia a sobreposição. Arquivos: [`exagero_nli_dev.json`](exagero_nli_dev.json), [`exagero_nli_test.json`](exagero_nli_test.json).

## O que fica para quem retomar

- **Modelo:** um LLM maior como verificador não cabe ao lado do principal na GPU atual. Um NLI genérico não separa as parciais. O que resta é hardware maior ou um verificador treinado para esse tipo de exagero. O `test` já foi usado uma vez: uma nova rodada com ajuste deve registrar isso.
- **Tempo:** o raciocínio ligado (`think`) é lento demais para cada frase no `gemma4:e4b`.
- **Amostra pequena:** o `test` tem só 5 parciais. Uma única parcial achada muda a taxa em 20 p.p. Mesmo assim, 0 de 5 e 36% no `dev` não chegam perto do critério.
