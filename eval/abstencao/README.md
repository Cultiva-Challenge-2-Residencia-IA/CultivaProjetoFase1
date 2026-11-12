# Conjunto do "não sei" (RF-IA01, issue #6)

`casos.json` mede quando o sistema deve dizer "não sei" em vez de responder. Ele é separado do golden set v2, que já foi revisado.

| Tipo | Casos | Esperado | O que mede |
|---|---:|---|---|
| `dentro` | 41 | responder | Perguntas que o corpus responde; a recusa aqui é indevida |
| `grafo_sem_corpus` | 1 | responder | Sem Trecho no corpus, mas com cadeia no grafo |
| `nutricao_fora_do_corpus` | 28 | não sei | Temas de Nutrição sem Trecho aprovado (kombucha, colágeno, krill...). Alguns do lote 2 têm menções no corpus (cetogênica, óleo de coco); a categoria é informativa |
| `fora_de_nutricao` | 26 | não sei | Fora do domínio (pneu, imposto, passaporte...) |

Cada caso traz a `origem`:
- **lote 1:** escrito pelo autor do código; um terço de cada tipo está no `test`;
- **lote 2:** escrito por MatheusSales2773 na revisão do PR #51, antes de ler o código. Entra só no `dev`, porque orientou a correção.

**Calibre só no `dev`.** O próximo lote cego deve vir de outra pessoa, num PR que não altere `src/rag/abstencao.py`.

## Como o "não sei" funciona

O "não sei" só vem quando a pergunta está **fora do domínio**, com os dois sinais apontando para fora:

1. o cosseno do Trecho mais próximo no ChromaDB (`HybridRetriever.similaridade_maxima`) fica abaixo de `ABSTENCAO_LIMIAR_COSSENO` (0,40); **e**
2. a pergunta não tem nenhum termo do vocabulário de Nutrição (`TERMOS_NUTRICAO` em `src/rag/abstencao.py`).

Nesse caso:

- **sem resultado do grafo ou da TACO:** resposta fixa, sem chamar o LLM, com `abstencao=True`;
- **com resultado do grafo ou da TACO:** responde só com eles (decisão da equipe de 12/11/2026).

Dentro do domínio, o fluxo segue normalmente, com os Trechos que a busca achou, mesmo com cosseno baixo.

A nota final do ranking não serve como sinal: desde a #35 ela é RRF puro e depende só da posição nas listas.

## Por que dois sinais (revisão do PR #51)

A primeira versão usava só o cosseno e recusava perguntas que o corpus responde:

| Pergunta | Cosseno | Evidência |
|---|---:|---|
| "Jejum intermitente funciona?" (persona Rafael, Premissa 2) | 0,24 | O BM25 traz Azevedo et al. (2013) e a ABESO nos 3 primeiros |
| "Como ler o rótulo para identificar um ultraprocessado?" | 0,36 | O BM25 traz o Guia em 1º e 2º |

O modelo de embeddings vai mal com perguntas curtas. O conjunto do lote 1 não pegava isso porque suas perguntas eram mais longas.

Sinais testados no `dev` (84 perguntas que devem ser respondidas, contando golden v2 e v1; 21 fora de Nutrição):

| Regra para "não sei" | Recusa indevida | Fora de Nutrição |
|---|---:|---:|
| cosseno < 0,40 | 6/84 | 18/21 |
| cosseno < 0,29 **e** cobertura dos termos ponderada pelo IDF < 0,66 | 0/84 | 14/21 (limite colado no caso do Rafael, frágil) |
| **cosseno < 0,40 e nenhum termo de Nutrição** | **0/84** | **18/21** |

O vocabulário só **impede** recusas: um termo que falte, no pior caso, deixa recusar uma pergunta de cosseno baixo. Os termos foram escritos a partir do domínio; `sono`, `dormir`, `absorção`, `cúrcuma` e `pimenta` entraram depois de ver perguntas do `dev` sem termo.

## Resultado (conjunto completo, 12/11/2026)

| Métrica | Valor | Mínimo no gate |
|---|---:|---:|
| Recusa indevida | **0/42** no conjunto e 0 no golden v2 e v1 | no máximo 5% |
| "Não sei" fora de Nutrição | 23/26 (88%); dev 18/21, test 5/5 | 85% |
| "Não sei" em Nutrição fora do corpus | 1/28 (informativo) | sem mínimo |

Fora de Nutrição e ainda respondidas:
- "Como trocar o óleo do carro?": "óleo" é termo do domínio;
- "Como estudar para o ENEM?" e "Me ajuda a fazer um currículo?": cosseno um pouco acima de 0,40. A do ENEM pertence à futura aba de Estudos (RF-IA06).

## Limite conhecido

Temas de Nutrição ausentes do corpus continuam sendo respondidos. Nenhum sinal local separa esse caso sem recusar perguntas boas, e ele está na issue #52 (verificação por LLM).

## Experimento: reranker cross-encoder (opção B, não adotado)

Para cada pergunta, os 8 primeiros Trechos da busca foram pontuados por um cross-encoder multilíngue do `fastembed`, já dependência do projeto, usando a maior nota como sinal. Os limiares abaixo são percentis das perguntas "dentro" (dev e golden).

| Modelo | Tempo por pergunta (CPU) | Nutrição fora do corpus | Recusa indevida |
|---|---:|---:|---:|
| `BAAI/bge-reranker-v2-m3-int8` (0,57 GB), limiar -3,42 | mediana 2,8 s, p95 4,8 s | **15/20** (dev 10/14, test 5/6) | golden 3/33, test 1/7 |
| `jinaai/jina-reranker-v2-base-multilingual` (1,1 GB), limiar -2,23 | mediana 1,4 s, p95 2,4 s | 10/20 | golden 3/33 |

O `bge-reranker-v2-m3` é o único sinal testado que separa parte dos temas de Nutrição ausentes do corpus: 15 de 20, contra 1 de 20 do cosseno. Ele não foi adotado agora por três motivos:

1. acrescenta cerca de 3 s por pergunta em CPU;
2. recusaria cerca de 9% das perguntas boas do golden set no limiar útil;
3. exige mais 0,57 GB de modelo.

Caminhos para uma próxima rodada: pontuar só os 4 Trechos finais (metade do tempo), combinar com o cosseno para proteger as perguntas longas do golden, ou usar um LLM julgando se os Trechos sustentam a resposta, junto com a verificação de fundamentação da #12.
