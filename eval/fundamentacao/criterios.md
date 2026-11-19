# Citações por frase e fundamentação (issue #12): critérios definidos antes da execução

Registrado em 17/11/2026, antes de medir.

**Requisitos:**
- **RN04:** os agentes citam a fonte da informação usada.
- **RNF27:** pelo menos 95% das afirmações sustentadas pelas fontes citadas, em amostra humana.
- **RF-IA01 e RN17:** a resposta explicativa traz fonte aprovada e clicável.

## Problema

Até aqui, as "citações" eram a lista de todos os Trechos recuperados, montada pelo código depois da resposta. O modelo não dizia de qual Trecho tirou cada frase. A checagem "toda citação aponta para um documento recuperado" (`citacoes_validas`, benchmark v2) passava sempre, sem mostrar se a resposta era sustentada.

## O que passa a valer

1. **Citação por frase.** O LLM recebe os Trechos numerados como `[T1]` a `[Tn]` e marca cada frase com os Trechos que a sustentam. Dados do grafo causal levam `[GRAFO]`, e da TACO, `[TACO]`.
2. **Checagem determinística** (`src/rag/verificador/citacoes.py`). O texto escrito pelo LLM (`evidence_summary`, `physiological_mechanism`, `protocol_findings`) é válido se:
   - toda frase com pelo menos 4 palavras tem ao menos um marcador;
   - todo `[T#]` está entre 1 e o número de Trechos recuperados;
   - `[GRAFO]` e `[TACO]` só aparecem quando há contexto do grafo ou da TACO;
   - há ao menos um `[T#]` quando há Trechos.

   A única frase aceita sem marcador é a frase fixa "Não consta nos trechos recuperados.", que o prompt manda usar quando o campo não tem base.
3. **Bloqueio.** Resposta do LLM que falha na checagem não chega ao usuário: a resposta passa a ser a síntese extrativa, que copia frases dos Trechos e marca cada uma com a origem. O motivo fica registrado na resposta (`fundamentacao_status` e `fundamentacao_problemas`).
4. **Citações exibidas.** São só os Trechos efetivamente citados, com o número `T#` e a página do PDF. O formato `[doc_id] …` é mantido para não quebrar o `citacoes_validas` do v2 nem a branch `langfuse`.

Os blocos gerados pelo código (síntese extrativa, TACO e grafo) não passam pela checagem: a origem deles é conhecida por construção. Um teste garante que a síntese extrativa só produz marcadores válidos.

## Medição com LLM (`qwen2.5:7b` local)

- **Conjunto:** perguntas do benchmark v2 (`eval/golden/v2/`) que chegam à síntese (sem risco, injeção, "não sei" ou recusa por prescrição).
- **Métricas:**
  - **conformidade de citação do LLM:** fração das respostas do LLM que passam na checagem, antes do bloqueio;
  - **taxa de fallback:** fração das respostas que caíram na síntese extrativa;
  - **problemas por tipo:** frase sem citação, marcador fora do intervalo, marcador de ferramenta sem a ferramenta, resposta sem nenhum `[T#]`.
- **Ajuste só no `dev`:** se a conformidade for baixa, o prompt pode ser ajustado olhando só o `dev`. O `test` roda uma vez, com o prompt final, e só mede.
- **Sem meta para a conformidade nesta issue.** O bloqueio garante que nenhuma resposta sem citação válida chega ao usuário, qualquer que seja a taxa. A taxa mostra quanto da resposta vem do LLM e quanto do fallback, e uma taxa baixa é registrada como limitação.

## Amostra humana de fidelidade (RNF27)

- **O que se julga:** frases das respostas do LLM que passaram na checagem, cada uma com o texto completo dos Trechos que ela cita. A pergunta é: o Trecho citado sustenta o que a frase afirma?
- **Amostra:**
  - **60 frases**, sorteadas com semente fixa;
  - no máximo 3 por resposta, de respostas do `dev` e do `test`;
  - se houver menos de 60 frases elegíveis, entram todas, e o número real é registrado.
- **Avaliador:** um colega que não escreveu este código nem o prompt. Ele julga sem ver a métrica de nenhuma outra frase.
- **Rubrica (`eval/fundamentacao/rubrica.md`):**
  - **sustentada:** o Trecho diz isso, com outras palavras ou não;
  - **parcial:** parte da frase está no Trecho e parte não, ou o Trecho diz algo mais fraco;
  - **não sustentada:** o Trecho não diz isso, diz o contrário ou é de outro assunto.
- **Meta do RNF27:** pelo menos 95% das frases julgadas como **sustentadas**. "Parcial" **não** conta como sustentada. O intervalo de Wilson de 95% é relatado junto, porque, com 60 frases, a meta pontual é compatível com taxas reais menores.
- **Enquanto o colega não avaliar, o RNF27 fica sem medição**, e isso é dito no PR.

## Adendo 1 (17/11/2026, depois da primeira medição no `dev`)

**Primeira medição** (prompt v1, `qwen2.5:7b`, 26 respostas do `dev` que chegaram ao LLM; `resultados_dev_prompt_v1.json`):
- conformidade de citação de **15,4%** (4 de 26) e fallback de 84,6%;
- problemas: 19 respostas com frase sem citação, 4 sem nenhum `[T#]` e 3 sem nenhuma frase.

O que a leitura das respostas mostrou:
- **O modelo de 7B quase não marca as frases**, mesmo quando elas vêm dos Trechos. O esquema JSON do prompt mostrava frases sem marcador, e o modelo copia o formato do esquema.
- **Em 3 perguntas, o LLM respondeu corretamente "Não consta nos trechos recuperados" nos três campos:** V2-FOR-01, V2-FOR-02 (fora de Nutrição) e V2-PRE-02. O bloqueio trocava isso pela síntese extrativa, que responde mesmo sem base, o que piora o RF-IA01.

**Mudanças, decididas só com o `dev`:**
1. **Prompt v2:** o esquema JSON passa a mostrar o marcador no fim de cada frase.
2. **Abstenção do LLM:** quando os três campos do LLM são a frase fixa (ou vazios), a resposta é a mensagem de "não sei" (`MENSAGEM_NAO_SEI`, `abstencao=True`, `fundamentacao_status="llm_sem_base"`), e não a síntese extrativa.

O `dev` é medido de novo com o prompt v2. O `test` continua sem ter sido rodado com LLM.

## Adendo 2 (19/11/2026, depois da medição do prompt v2 no `dev`)

**Medição do prompt v2** (`medicao_dev_prompt_v2_parcial.log`). Ela parou na pergunta V2-TAC-01, por um bug: o código tratava `[TACO]` como um `[T#]`, porque também começa com "T", e tentava converter "ACO" em número. A medição também derrubaria uma resposta real em que o LLM usasse `[TACO]`; foi corrigido com `eh_trecho` e um teste. **Até a parada:**
- 3 de 20 respostas checadas passaram (15%), o mesmo nível do v1;
- as 3 perguntas em que o LLM disse "não consta" viraram "não sei" (V2-FOR-01, V2-FOR-02, V2-PRE-02), como pretendido.

**Mudança, decidida só com o `dev`** e sugerida também na revisão do PR #61:

- **Prompt v3, formato estruturado.** Cada campo do LLM passa a ser uma lista de `{"frase": …, "trechos": [números, "TACO" ou "GRAFO"]}`.
- **Conversão para a mesma checagem.** O código (`normalizar_frases_citadas`) monta o texto com os marcadores no fim de cada frase e aplica a mesma checagem de antes. Referências fora do formato viram um marcador inválido e reprovam.
- **Compatibilidade.** Respostas em texto continuam aceitas.

## Issue #67: citação literal e mecanismo opcional (critérios registrados em 19/11/2026, antes de medir)

**Ponto de partida** (PR #68): na amostra de 60 frases do prompt v3, julgada com o ChatGPT, só 35% das frases eram sustentadas pelo trecho citado (`physiological_mechanism`: 17%). A checagem da #12 confere a forma da citação, não o conteúdo.

**Prompt v4:**
- **Citação literal:** cada item é `{"frase", "trechos", "citacao"}`, e `citacao` é um pedaço copiado, sem alterar, de um dos trechos citados (ou do bloco da TACO ou do grafo), que sustente a frase.
- **Mecanismo opcional:** `physiological_mechanism` só traz frases quando um trecho descreve o mecanismo; caso contrário, vem a frase fixa "Não consta nos trechos recuperados.".

**Checagem determinística da citação literal** (`src/rag/verificador/citacoes.py`), sem LLM. Uma frase é válida se:
- a `citacao` tem pelo menos **4 palavras**;
- normalizada (caixa, acentos compatíveis por NFKC, pontuação e espaços), a `citacao` aparece **como sequência contínua** no texto normalizado de pelo menos uma das fontes que a frase cita (`[T#]`, `[TACO]` ou `[GRAFO]`).

A frase fixa "Não consta nos trechos recuperados." dispensa citação.

**Decisão do responsável (MatheusSales2773, 19/11/2026):** a frase sem citação literal válida é **removida**, e as demais seguem. A resposta só cai na síntese extrativa se o `evidence_summary` ficar sem nenhuma frase. Depois da remoção, continua valendo a checagem da #12 (marcadores no intervalo, ao menos um `[T#]`). Se o LLM disser "Não consta" nos três campos, a resposta segue sendo o "não sei".

**Medições (`qwen2.5:7b` local):**
- conformidade antes do bloqueio, taxa de resposta extrativa, frases removidas por resposta e mediana de tempo;
- ajuste do prompt só olhando o `dev`; o `test` roda uma vez, com o prompt final.

**Comparação com os 35%:**
- **Amostra:** 60 frases novas, sorteadas como na #12 (semente fixa, no máximo 3 por resposta), entre as frases que **chegam ao usuário**.
- **Juiz:** o ChatGPT, com a mesma rubrica, para comparar com o mesmo juiz. Resultado registrado como estimativa por juiz automático.
- **Leitura:** a mudança é considerada **eficaz** se a fidelidade subir pelo menos 20 p.p. em relação aos 35% (ou seja, chegar a 55% ou mais), e se o limite inferior do intervalo de Wilson ficar acima de 35%. A meta do RNF27 (95%) continua sendo a referência; não atingi-la é relatado como tal.

### Adendo à #67 (19/11/2026, depois da primeira medição do v4 no `dev`)

**Primeira medição** (`medicao_dev_prompt_v4a.log`, `resultados_dev_prompt_v4a.json`):
- 16 de 23 respostas aceitas e 7 caídas na extrativa por citação;
- 18 frases removidas e 34 mantidas;
- 4 respostas passaram dos 45 s.

**O que a leitura das frases removidas mostrou:** várias citações eram **literais e verdadeiras, mas com o rótulo errado**. O modelo copiava texto do bloco da TACO ou do grafo e o marcava como trecho [4] ou [1] (V2-TAC-01, V2-TAC-02, V2-GRA-01). Num caso, a citação diferia só no espaço entre número e unidade ("800kcal" × "800 kcal", V2-PRE-01).

**Ajustes, decididos só com o `dev`:**
1. **Rótulo corrigido:** se a citação literal não está na fonte citada, mas está em **outra fonte entregue ao modelo**, a frase fica e o rótulo é **corrigido** para a fonte onde a citação está (registrado em `rotulos_corrigidos`). A exigência de que a citação exista literalmente no material entregue não muda.
2. **Número e unidade:** na busca, um número colado a letras é separado delas ("800kcal" = "800 kcal").

## Modelo `gemma4:e4b` com o prompt v4 (critérios registrados em 19/11/2026, antes de medir)

**Motivo:** o PR #70 (issue #55) recomenda trocar o `qwen2.5:7b` pelo `gemma4:e4b`, mas mediu com prompts congelados **antes** da #12 e sugere rodar os finalistas de novo com o prompt atual antes da troca. Esta medição dá esse dado para o ADR 0004. A troca de `OLLAMA_MODEL` continua com a #55: aqui o modelo é escolhido só por variável de ambiente, na medição.

**Igual à medição do `qwen2.5:7b`:** prompt v4, checagem de citação literal, `dev` e `test` (sem ajuste nenhum: prompt e regras ficam congelados como no #75), amostra de até 60 frases com a mesma semente, a mesma rubrica e o mesmo juiz (ChatGPT). Resultados com o rótulo `gemma4_e4b`, sem sobrescrever os do `qwen2.5:7b`.

**Leitura:**
- **O que é relatado:** respostas aceitas, frases removidas, rótulos corrigidos, latência e fidelidade com IC de Wilson, lado a lado com o `qwen2.5:7b` (46%, IC de 34% a 58%).
- **Quando há diferença:** a fidelidade só é declarada **diferente** se os ICs de Wilson **não se sobrepuserem**. Com ICs sobrepostos, o resultado é **empate técnico**, e a latência e a taxa de respostas aceitas desempatam.
- **RNF27:** a meta de 95% continua sendo a referência.
