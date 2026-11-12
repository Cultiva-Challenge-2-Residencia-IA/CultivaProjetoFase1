# Conjunto do "não sei" (RF-IA01, issue #6)

`casos.json` mede quando o sistema deve dizer "não sei" em vez de responder. Ele é separado do golden set v2, que já foi revisado.

| Tipo | Casos | Esperado | O que mede |
|---|---:|---|---|
| `dentro` | 21 | responder | Perguntas curtas que o corpus responde; a recusa aqui é indevida |
| `grafo_sem_corpus` | 1 | responder | Sem Trecho no corpus, mas com cadeia no grafo |
| `nutricao_fora_do_corpus` | 20 | não sei | Temas de Nutrição com zero Trechos aprovados (kombucha, colágeno, krill...), conferidos por busca textual em 12/11/2026 |
| `fora_de_nutricao` | 16 | não sei | Fora do domínio (pneu, imposto, dengue...) |

Um terço de cada tipo está no split `test`. **Calibre só no `dev`.**

## Como o "não sei" funciona

Depois da busca, o consultor calcula o cosseno do Trecho mais próximo no ChromaDB (`HybridRetriever.similaridade_maxima`). Abaixo de `ABSTENCAO_LIMIAR_COSSENO`, em `src/config.py`:

- **sem resultado do grafo ou da TACO:** resposta fixa (`src/rag/abstencao.py`), sem chamar o LLM, com `abstencao=True`;
- **com resultado do grafo ou da TACO:** responde só com eles, sem os Trechos abaixo do limiar. Decisão da equipe de 12/11/2026.

A nota final do ranking não serve como sinal. Desde a #35 ela é RRF puro e depende só da posição nas listas: o 1º colocado tem nota parecida para qualquer pergunta.

## Limite conhecido

O cosseno mede se a pergunta é **do mesmo assunto** que algum Trecho, não se algum Trecho **responde** a pergunta. Por isso:

- **fora de Nutrição** separa bem: pneu tem cosseno 0,07, imposto 0,24;
- **Nutrição fora do corpus** não separa: "Kombucha ajuda a emagrecer?" chega a 0,63, mais alto que várias perguntas que o corpus responde (mínimo de 0,42). Para pegar esses casos só com o cosseno, seria preciso recusar cerca de um quarto das perguntas boas.

`nao_sei_nutricao_fora_do_corpus` aparece no relatório, mas fica sem mínimo no gate.

## Gate (`eval/gates.toml`, seção `[abstencao]`)

| Métrica | Mínimo |
|---|---:|
| `nao_sei_fora_de_nutricao` | 0,90 |
| `respostas_esperadas` (o complemento da recusa indevida) | 0,95 |

## Calibração do limiar (dev, 12/11/2026)

O limiar 0,40 é o maior em que nenhuma pergunta que deve ser respondida foi recusada: 0 de 14 no dev, 0 de 7 no test e 0 de 49 perguntas do golden set v2 e do benchmark v1. A pergunta "dentro" de menor cosseno ficou em 0,416, então a margem é pequena.

| Limiar | Recusa indevida (dev + golden) | Fora de Nutrição (dev) | Nutrição fora do corpus (dev) |
|---:|---:|---:|---:|
| 0,35 | 0/63 | 9/11 | 0/14 |
| **0,40** | **0/63** | **10/11** | **1/14** |

No test: 0/7 de recusa indevida, 5/5 fora de Nutrição e 1/6 de Nutrição fora do corpus. A única pergunta fora de Nutrição respondida no dev é "Como estudar para o ENEM?" (0,416). Ela pertence à futura aba de Estudos, que pelo RF-IA06 deve receber uma mensagem indicando a aba certa.

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
