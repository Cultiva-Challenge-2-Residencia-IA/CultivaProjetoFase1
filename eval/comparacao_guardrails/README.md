# Comparação de frameworks de guardrail (issue #52)

Mede se um framework de guardrail de mercado deve entrar no CULTIVA para duas coisas que as camadas locais não resolvem:

1. o "não sei" em temas de Nutrição ausentes do corpus (kombucha, colágeno), que hoje são respondidos;
2. a verificação de fundamentação: se a resposta é sustentada pelos Trechos (RNF27, #12).

Os dois problemas pedem o mesmo julgamento: **a resposta é sustentada pelos Trechos?** Se não for, ela vira "não sei".

Critérios e regra de decisão, registrados antes de medir: [`criterios.md`](criterios.md). Resultados: [`resultados.md`](resultados.md) e `resultados.json`.

## Decisão (20/11/2026, `gemma4:e4b` na RTX 5060)

Pela regra registrada em `criterios.md`:

- **"Não sei": nenhum candidato é elegível. Ficam só as camadas locais.** O limite é recusa indevida de no máximo 5% no golden v2 e no "dentro" da abstenção, somados (73 perguntas). As camadas locais recusam 1 de 73. Com cada candidato, as recusas indevidas sobem para:
  - `direto_pre`: 20 de 73 (27%);
  - `direto_pos`: 20 de 73 (27%);
  - `nemo`: 31 de 73 (42%);
  - `guardrails_ai`: 61 de 73 (84%).

  Os candidatos dão mais "não sei" em Nutrição fora do corpus (de 6 de 28 para até 22 de 28), mas recusam junto perguntas que o corpus responde. A Nutrição fora do corpus continua sem solução e fica registrada como limitação.
- **Fundamentação: vence a chamada direta (`direto_pos`).** São elegíveis (fiel aceita de pelo menos 90%):
  - `direto_pos`: 19 de 20;
  - `guardrails_ai`: 19 de 20.

  O `nemo` fica de fora (17 de 20). Os dois elegíveis barram todas as respostas inventadas e trocadas, então o Guardrails AI não supera a chamada direta em 10 p.p. e o empate vai para a chamada direta. Ela também é cerca de 19 vezes mais rápida (p50 de 1,0 s contra 18,8 s).
- **Nada entra na produção por este PR.** Ligar a verificação depois de gerar exige resolver antes a recusa indevida medida acima. O `direto_pos` julgou não sustentadas 19 das 64 respostas do golden v2 e da abstenção que passaram na validação de citações da #61. Isso fica para uma issue própria, com medição na GPU de referência.

### Limitações

- Os conjuntos são pequenos (6 casos no `test`, 28 de Nutrição fora do corpus e 20 por tipo na fundamentação). Os intervalos de Wilson se sobrepõem na maior parte das comparações.
- Os casos `trocada` são fáceis: todos os candidatos barram 20 de 20. A diferença entre candidatos aparece na `inventada` e nas respostas reais.
- As frases reais da amostra da #12 têm rótulos do juiz automático do #68, sem revisão humana. Por isso entram só como apoio. Nesse conjunto, o `direto_pos` aceita todas as sustentadas e barra 59% das não sustentadas (kappa 0,50).
- O `guardrails_ai` recusou as 8 respostas extrativas, que copiam frases dos próprios Trechos. Isso sugere que o `ProvenanceLLM` com os 3 Trechos mais próximos não serve para respostas em português neste corpus, sem ajuste. Nenhum prompt ou parâmetro foi ajustado, conforme os critérios.
- Os critérios previam medir na GTX 1650 (4 GB), com tempo só indicativo. A medição completa foi refeita na RTX 5060, a GPU de referência, e os vereditos parciais da 1650 foram descartados. Os critérios e os prompts não mudaram.
- Um só modelo (`gemma4:e4b`, ADR 0004), com temperatura 0. Outro modelo pode mudar o resultado.

## Candidatos

Todos com o mesmo LLM do Ollama local (ADR 0003):

| Candidato | O que é |
|---|---|
| `direto_pre` | Chamada direta ao LLM antes de gerar: os Trechos respondem a pergunta? |
| `direto_pos` | Chamada direta ao LLM depois de gerar: a resposta é sustentada pelos Trechos? |
| `nemo` | NeMo Guardrails, trilho de saída `self check facts`, com o prompt da documentação |
| `guardrails_ai` | Guardrails AI, validador `ProvenanceLLM`, frase a frase, com os 3 Trechos mais próximos |

**Telemetria do Guardrails AI:** por padrão, ele envia rastros (OpenTelemetry) a um servidor externo. O código desliga isso (`OTEL_SDK_DISABLED=true` e `enable_metrics=False`), sem depender do `~/.guardrailsrc` de quem roda. Quem for usar o Guardrails AI fora deste script precisa fazer o mesmo, ou rodar `guardrails configure --disable-metrics`.

**NLTK:** o `ProvenanceLLM` divide a resposta em frases com o `punkt` do NLTK. O NLTK se recusa a ler e gravar em `~/nltk_data` se a pasta puder ser alterada por outros usuários; nesse caso, rode `chmod go-w ~/nltk_data`.

## Conjuntos

- **"Não sei":** as perguntas de `eval/abstencao/casos.json` e as do golden v2 que esperam resposta. O sistema atual gera a resposta de cada uma (`respostas`), e cada candidato a julga. O que as camadas locais já recusaram não vai ao candidato: elas são o piso.
- **Fundamentação** (`casos_fundamentacao.json`, gerado por `casos.py`): para 20 perguntas do golden v2, uma resposta fiel (frases dos Trechos), uma com uma afirmação inventada e uma com frases dos Trechos de outra pergunta.

## Como rodar

```bash
uv sync --group guardrails-frameworks          # NeMo Guardrails, Guardrails AI e PyTorch para CPU
# Ollama e modelo (padrão: OLLAMA_BASE_URL e OLLAMA_MODEL de src/config.py)
export COMPARACAO_GUARDRAILS_OLLAMA_URL=http://127.0.0.1:11434
export COMPARACAO_GUARDRAILS_MODELO=gemma4:e4b    # padrão: OLLAMA_MODEL (gemma4:e4b, ADR 0004)
export COMPARACAO_GUARDRAILS_MAQUINA=gtx1650-4gb   # fora da GPU de referência: tempo só indicativo
uv run python -m src.evaluation.comparacao_guardrails casos          # regrava casos_fundamentacao.json
uv run python -m src.evaluation.comparacao_guardrails respostas      # respostas do sistema atual
uv run python -m src.evaluation.comparacao_guardrails fundamentacao
uv run python -m src.evaluation.comparacao_guardrails fundamentacao-reais   # apoio: amostra da #12 avaliada no #68
uv run python -m src.evaluation.comparacao_guardrails abstencao
uv run python -m src.evaluation.comparacao_guardrails relatorio
```

Cada etapa é retomável. As respostas saem do pipeline de produção (LangGraph, ADR 0004: `num_ctx` 8192, raciocínio desligado e até 2048 tokens de saída). As respostas e os vereditos brutos ficam em `data/comparacao_guardrails/` (fora do Git). Fora do CI: a camada com LLM não roda no CI, que é offline.
