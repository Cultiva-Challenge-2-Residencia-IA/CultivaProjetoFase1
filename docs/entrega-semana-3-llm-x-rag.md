# Semana 3: comparação LLM x RAG e avaliação da geração

Benchmark comparativo de respostas: `src/evaluation/benchmark_respostas.py`, golden set em `eval/golden/resposta/` e relatório em `eval/runs/respostas/relatorio_respostas_comparativo.md` (dados em `data/benchmark/relatorio_respostas_comparativo.json`).

!!! abstract "Resultado em uma frase"
    Com o modelo local do ADR 0004 (`gemma4:e4b`), **a LLM escrevendo sobre os Trechos é melhor que a síntese extrativa** em todos os recortes. **RAG e LLM sem RAG empatam** na régua de termos. A diferença que a régua não mede é a auditabilidade: só o RAG cita a fonte de cada frase (RN04).

## 1. O que foi pedido e o que foi entregue

| Exigência da Semana 3 | Situação | Onde |
|---|---|---|
| Comparar LLM com RAG | Feito, com as mesmas perguntas e teste pareado | Seções 2 e 3 |
| Ir além de palavras-chave | Parcial: régua com fatos essenciais, afirmações proibidas, segurança e fidelidade ao contexto. Ainda é baseada em termos (seção 4) | `avaliar_execucao` |
| Testar formas diferentes de usar o RAG | Feito: 4 condições | Seção 2 |
| Escolher a melhor configuração | Feito: RAG com LLM local, guardrails e síntese extrativa como último recurso | Seção 5 |
| Observabilidade | Opcional: `--use-langfuse` envia traces e scores ao Langfuse (grupo `observabilidade`, destino local por padrão, ADR 0003) | `obter_cliente_langfuse` |

## 2. As 4 condições

Todas recebem a mesma pergunta, passam pelos mesmos guardrails da Lei 8.234/1991 e, quando usam LLM, chamam o mesmo modelo com as mesmas opções de produção (ADR 0004: `gemma4:e4b`, `think` desligado, `num_ctx` 8192, `num_predict` 2048).

| # | Condição | O que o modelo recebe | Para que serve |
|---|---|---|---|
| 1 | `llm_sem_rag` | Só a pergunta | Linha de base: o que o modelo sabe sozinho (não é modo do produto) |
| 2 | `rag_extrativo` | Busca híbrida, sem LLM: a resposta copia frases dos Trechos | O último recurso do produto quando não há LLM |
| 3 | `rag_atual` | O consultor completo: busca, TACO, grafo, citação por frase (#12) e guardrails | O que o usuário recebe |
| 4 | `contexto_oracle` | Os Trechos ideais do gabarito, sem busca | O teto: separa erro de busca de erro de síntese |

## 3. Resultados (`dev`, 36 casos, 19/11/2026)

**Casos:**
- os **20** do gabarito de respostas (`eval/golden/resposta/dev.json`, escritos e revisados à mão);
- mais **16** do golden v2 `dev` (`--incluir-golden-v2`): as perguntas que devem ser respondidas e têm termos obrigatórios, com os Trechos julgados relevantes como contexto oráculo e a cobertura dos termos do v2 como completude. A pergunta repetida (V2-REC-01, a mesma do RESP-DIR-01) ficou de fora.

**Execução:** RTX 5060, 7 minutos, **nenhuma falha de medição**.

**Na `rag_atual`:**
- 29 respostas do LLM com citações válidas;
- 2 "não sei" do próprio LLM;
- 1 síntese extrativa depois de citação inválida;
- 4 respostas fixas (risco, injeção ou "não sei" do cosseno).

| Condição | Nota geral | IC 95% | Correção factual | Completude | Citações válidas |
|---|---:|---|---:|---:|---:|
| `contexto_oracle` | 0,613 | [0,498; 0,727] | 61,4% | 51,0% | 100% |
| `rag_atual` | 0,604 | [0,497; 0,710] | 62,5% | 42,8% | 16,7% |
| `llm_sem_rag` | 0,581 | [0,480; 0,682] | 56,0% | 41,6% | não se aplica |
| `rag_extrativo` | 0,517 | [0,411; 0,624] | 50,2% | 31,8% | 0% |

### Teste pareado: quem ganha de quem

Como as quatro condições respondem às mesmas perguntas, a comparação certa é a **diferença caso a caso**, com intervalo de confiança por bootstrap pareado (10.000 reamostras). Se o intervalo contém o zero, é empate técnico. Comparar só os intervalos de cada condição, como na tabela acima, é grosseiro demais.

| Comparação | Todos (36) | Golden v2 (16) | Perguntas a responder (25) |
|---|---|---|---|
| RAG atual − LLM sem RAG | −0,02 [−0,12; +0,08], empate | +0,05 [−0,10; +0,20], empate | +0,04 [−0,09; +0,16], empate |
| Oráculo − LLM sem RAG | +0,03 [−0,05; +0,12], empate | **+0,16 [+0,06; +0,27]** | +0,08 [−0,03; +0,19], empate |
| RAG atual − RAG extrativo | **+0,09 [+0,03; +0,15]** | **+0,07 [+0,01; +0,15]** | **+0,10 [+0,03; +0,18]** |

**Leitura:**
1. **A LLM sobre os Trechos é melhor que a síntese extrativa.** É o único resultado firme em todos os recortes, e ele justifica a LLM no produto, com a extrativa só como último recurso.
2. **RAG e LLM sem RAG empatam.** Pela régua de termos, o `gemma4:e4b` responde boa parte destas perguntas com o próprio conhecimento.
3. **O contexto ideal ajuda no golden v2** (+0,16 sobre o LLM sem RAG). O RAG atual fica no meio (0,84, contra 0,95 do oráculo). A distância até o teto é a perda na busca e na síntese.
4. **No gabarito escrito à mão, o oráculo não ganha nem do LLM sem RAG.** Isso aponta um limite da régua, não da condição (seção 4).

## 4. Limitações

- **A régua é por termos.** Ela confere se as palavras dos fatos essenciais aparecem e se as afirmações proibidas não aparecem; a negação só vale na mesma frase da afirmação. Ela não entende a resposta: uma resposta correta com outras palavras perde ponto. Isso explica o oráculo abaixo do LLM sem RAG no gabarito escrito à mão.
- **A régua não mede fundamentação.** O LLM sem RAG pode acertar sem ter de onde tirar a informação. O valor do RAG para o produto, que é toda frase rastreável a um Trecho aprovado (RN04, RF-IA01), aparece em "citações válidas" e na checagem da #12, não na nota geral. A fidelidade de conteúdo do `gemma4:e4b` é medida à parte (#67, amostra humana do RNF27 na #12).
- **Amostra pequena:** 36 casos, dos quais 25 a responder. Diferenças menores que uns 10 pontos não se separam do ruído.
- **O `test` do gabarito de respostas (6 casos) ainda não foi revisado** por uma segunda pessoa e não foi rodado. Ele continua como holdout.
- **LLM com temperatura 0,1:** duas execuções seguidas não são idênticas. Na mesma configuração, a nota do RAG atual nos 20 casos do gabarito variou de 0,433 para 0,418.

**Próximo passo para a régua:** um juiz LLM às cegas, como o da #55 (escolha do modelo local), que julga se cada afirmação é correta frente aos Trechos de referência.

## 5. Decisão para o produto

Fica a configuração atual: **RAG híbrido com a LLM local do ADR 0004, citação por frase com bloqueio (#12), guardrails da Lei 8.234/1991 e síntese extrativa como último recurso.**
- O ganho da LLM sobre a extrativa é medido e significativo.
- O RAG não ganhou do LLM sem RAG na nota, mas é o que permite citar a fonte de cada frase, um requisito do produto (RN04) que o LLM sem RAG não cumpre.

## 6. Como rodar

```bash
# Sem LLM (determinístico; as condições com LLM viram respostas fixas)
uv run python -m src.evaluation.benchmark_respostas --split dev --no-llm

# Com o modelo local do ADR 0004 e os 16 casos de resposta do golden v2 (cerca de 7 min na RTX 5060)
uv run python -m src.evaluation.benchmark_respostas --split dev --use-ollama --incluir-golden-v2

# Revisão humana às cegas (chave em arquivo separado)
uv run python -m src.evaluation.benchmark_respostas --split dev --no-llm --export-blind eval/golden/resposta/revisao_cega_dev.json

# Traces no Langfuse (opcional: uv sync --group observabilidade; destino local por padrão)
uv run python -m src.evaluation.benchmark_respostas --split dev --use-ollama --use-langfuse
```
