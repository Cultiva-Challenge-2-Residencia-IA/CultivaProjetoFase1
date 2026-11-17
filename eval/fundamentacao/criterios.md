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
