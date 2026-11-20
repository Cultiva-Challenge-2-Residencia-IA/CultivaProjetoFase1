# Comparação de frameworks de guardrail (issue #52): critérios definidos antes da execução

Registrado em 19/11/2026, antes de rodar os candidatos nos conjuntos de medição. Só um teste de funcionamento com duas respostas inventadas pelo autor, fora dos conjuntos, foi feito antes.

## Pergunta

Um framework de guardrail de mercado deve entrar no CULTIVA para:

1. dizer "não sei" em temas de Nutrição ausentes do corpus, que hoje são respondidos (1 de 28 com as camadas locais da #6);
2. verificar se a resposta é sustentada pelos Trechos (RNF27, #12)?

As saídas possíveis são três: adotar um framework, chamar o LLM direto ou manter só as camadas locais.

## Candidatos

Todos usam o mesmo LLM, do Ollama local, com temperatura 0 (ADR 0003): `COMPARACAO_GUARDRAILS_MODELO`, padrão `gemma4:e4b`, o modelo principal escolhido na #55 (PR #70). As respostas julgadas também são geradas por ele.

| Candidato | Como decide | Prompt |
|---|---|---|
| `direto_pre` | Antes de gerar: os Trechos respondem a pergunta? | Escrito para a #52, antes de medir |
| `direto_pos` | Depois de gerar: a resposta é sustentada pelos Trechos? | Escrito para a #52, antes de medir |
| `nemo` | NeMo Guardrails 0.25, trilho de saída `self check facts` | O da documentação do NeMo, sem ajuste |
| `guardrails_ai` | Guardrails AI 0.11, `ProvenanceLLM` frase a frase, com os 3 Trechos mais próximos por embeddings | O do validador, sem ajuste |

O `RestrictToTopic` do Guardrails AI e os trilhos de tópico em Colang do NeMo não entram: eles decidem pelo assunto da pergunta, como o vocabulário da #6, e o problema é um tema de Nutrição que o corpus não cobre.

**Telemetria:** o Guardrails AI envia rastros a um servidor externo por padrão. Ela fica desligada no código (`OTEL_SDK_DISABLED` e `enable_metrics=False`).

## Conjuntos

- **"Não sei":** as 95 perguntas de `eval/abstencao/casos.json` e as 31 do golden v2 que esperam resposta. O sistema atual gera uma resposta para cada uma (`respostas`), e cada candidato a julga.
  - O recorte oficial da issue é o `test` (6 de Nutrição fora do corpus). Como nenhum candidato foi calibrado em nenhum split, o resultado com as 28 também é relatado, e a decisão olha os dois.
  - **Piso:** quando as camadas locais já deram "não sei" ou o alerta de risco, o candidato não é consultado, e a resposta continua "não sei". Nenhuma camada nova desfaz uma recusa local.
- **Fundamentação** (`casos_fundamentacao.json`, `casos.py`): para 20 perguntas do golden v2 (as que têm ao menos três frases completas nos Trechos de nota 2), três respostas montadas com os Trechos de nota 2:
  - `fiel`: três frases copiadas dos Trechos (sustentada);
  - `inventada`: a fiel mais uma afirmação plausível que não está nos Trechos (não sustentada; só uma frase em quatro é falsa);
  - `trocada`: três frases dos Trechos de outra pergunta, sem frase em comum com os Trechos desta (não sustentada).

- **Apoio: frases reais da amostra da #12** (PR #68): as 60 frases do `qwen2.5:7b`, cada uma com os Trechos que ela cita, julgadas pelo ChatGPT (21 sustentadas, 24 parciais, 15 não sustentadas). Como no #68, "parcial" conta como não sustentada. Os rótulos vêm de um juiz automático, então este conjunto é **só informativo** e fica fora da regra de decisão.

## Métricas

- **"Não sei" em Nutrição fora do corpus:** fração com "não sei" (principal).
- **Recusa indevida:** fração com "não sei" nas perguntas que o corpus responde (golden v2 e "dentro" da abstenção).
- **Fundamentação:** fiel aceita, inventada barrada e trocada barrada, cada uma com o intervalo de Wilson de 95%.
- **Apoio (frases reais):** concordância com os rótulos do #68, sustentada aceita, não sustentada barrada e kappa de Cohen.
- **Custo:** tempo por pergunta (p50 e p95) e chamadas ao LLM por pergunta. A medição roda na GTX 1650 de 4 GB (decisão de 19/11/2026), e o tempo é **só indicativo**: não representa a GPU de referência.

## Regra de decisão

1. **Elegível para o "não sei"** é o candidato com recusa indevida de no máximo 5% (o limite do gate `[abstencao]`) no golden v2 e no "dentro" da abstenção, somados.
2. **Elegível para a fundamentação** é o candidato que aceita pelo menos 90% das respostas fiéis.
3. Entre os elegíveis, o melhor é o de maior "não sei" em Nutrição fora do corpus (todas as 28) e, na fundamentação, o de maior média entre inventada barrada e trocada barrada.
4. **Um framework só é adotado se superar a chamada direta** (a melhor entre `direto_pre` e `direto_pos`) em pelo menos 10 p.p. na métrica principal da tarefa, sem recusa indevida maior. Diferença menor conta como empate, e no empate vence a chamada direta: tem menos dependências e o prompt fica no código.
5. **Se nenhum candidato for elegível**, ficam só as camadas locais, e o resultado é registrado como limitação.
6. Com 6 casos no `test` e 28 no total, intervalos que se sobrepõem são relatados como tal. A decisão desta issue é sobre **qual caminho seguir**. Ligar a camada na produção depende de medir o tempo na GPU de referência e de um PR próprio.

O `test` da abstenção e do golden v2 só mede: nada é ajustado a partir dele.
