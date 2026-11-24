# Checagem de exagero (issue #86): critérios definidos antes da medição

Registrado em 21/11/2026, antes de rodar o verificador em qualquer frase. Este arquivo é commitado
antes do código de avaliação produzir resultados; o histórico do Git mostra a ordem.

## O que se mede

O verificador (`src/rag/verificador/exagero.py`) recebe uma frase da resposta, sem os marcadores, e o
texto dos Trechos que ela cita, e responde se os Trechos sustentam tudo o que a frase afirma. Ele roda
sobre as 120 frases já julgadas pelo ChatGPT com a `rubrica.md`:

| Conjunto | Sustentadas | Parciais |
|---|---:|---:|
| `dev` (amostras v4 e v5 do `gemma4:e4b`) | 73 | 14 |
| `test` | 28 | 5 |

Métricas, por conjunto:

- **parciais achadas:** parciais que o verificador marca como não sustentadas / total de parciais;
- **remoção indevida:** sustentadas que o verificador marca como não sustentadas / total de sustentadas;
- **taxa projetada:** sustentadas mantidas / (sustentadas mantidas + parciais mantidas), isto é, a
  porcentagem de frases sustentadas que restaria na amostra se as marcadas fossem removidas;
- **falhas:** chamadas sem veredito (erro ou tempo limite), que no produto mantêm a frase;
- **tempo mediano por frase.**

## Regras

1. **Ajustes só no `dev`.** No máximo três versões do prompt do verificador, todas registradas com os
   números do `dev`. O `test` é rodado uma única vez, com a versão final.
2. **Se a primeira versão for usada sem ajuste**, nenhuma frase influenciou o verificador, e a decisão
   usa as 120 frases juntas (o `test` sozinho tem só 5 parciais). Se houver ajuste, a decisão usa só o
   `test`, e o `dev` fica como diagnóstico.
3. **Ligar no produto** só se, no conjunto da decisão: parciais achadas ≥ 50% **e** remoção indevida
   ≤ 10%. Caso contrário, o resultado é registrado e a proposta fica sem ligar.
4. O prompt usa categorias genéricas de exagero (condição, público, dose, força da afirmação,
   atribuição, acréscimo). Essas categorias vêm da análise publicada das parciais v4 e v5, que inclui
   frases do `test`; os exemplos do prompt não são frases das amostras.
5. Uma chamada por frase, com o `gemma4:e4b` local (ADR 0003), temperatura 0 e semente fixa.
6. Se ligar, a confirmação é a do critério da issue: `fundamentacao medir` no `dev` e no `test` e uma
   amostra nova de 60 frases julgada com o `prompt_juiz.md`.

## Adendo: segundo verificador, modelo de NLI (21/11/2026, antes de rodar)

Escrito depois do resultado do `gemma4:e4b` (0 de 5 parciais no `test`) e antes de rodar o modelo abaixo em qualquer frase.

- **Por quê:** o modelo principal não deve mudar, e um segundo LLM do mesmo porte não cabe junto na GPU de 8 GB. Um modelo de inferência textual (NLI) é pequeno, roda no processador e é treinado para a pergunta "o texto A garante o texto B?".
- **Modelo, fixado agora:** `MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7`, local, no processador. Não será trocado por outro modelo dentro desta medição.
- **Entrada:** premissa = texto de cada Trecho citado; hipótese = a frase sem marcadores. Até 512 tokens, com truncamento só da premissa. A pontuação da frase é a maior probabilidade de `entailment` entre os Trechos que ela cita.
- **Veredito:** a frase é marcada quando a pontuação fica abaixo de um limiar. O limiar é o único ajuste: é escolhido no `dev` como o maior valor com remoção indevida ≤ 10% no `dev`, e congelado antes de rodar o `test` uma única vez.
- **Decisão:** a mesma regra 3 (parciais achadas ≥ 50% **e** remoção indevida ≤ 10%), só no `test`.
- **Ressalva:** o `test` já foi usado uma vez, com o `gemma4:e4b`. Nada daquela rodada influenciou esta além do conhecimento de que ela falhou, e esta é a segunda tentativa sobre o mesmo conjunto.
