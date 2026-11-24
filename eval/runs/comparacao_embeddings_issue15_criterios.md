# Comparação de modelos de embeddings: critérios definidos antes da execução (issue #15)

Registrado em 24/11/2026, antes de rodar qualquer candidato novo. Resultados e decisão: [`comparacao_embeddings_issue15.md`](comparacao_embeddings_issue15.md).

## Pergunta

Algum modelo de embeddings local, em português, recupera melhor os Trechos do corpus de Nutrição que o modelo atual (`paraphrase-multilingual-MiniLM-L12-v2`), sem piorar o "não sei" nem o gate do CI?

## Por que comparar (motivo independente da métrica)

- O modelo atual trunca a entrada em **128 tokens** (`max_length` do tokenizer no fastembed). Um Trecho tem cerca de 1.000 caracteres, perto de 250 tokens: só a primeira metade de cada Trecho vira vetor.
- A issue pede pelo menos dois modelos comparados em português no golden set, e um provedor que não use os dados para treino (RNF05).

## Candidatos (fixados antes da execução)

Todos rodam localmente pelo `fastembed` (ONNX, CPU), já dependência do projeto: nenhum Trecho nem pergunta sai da máquina. O BGE-M3 ficou de fora porque o `fastembed` 0.9.1 não o oferece e o Ollama não existe no CI. O `jinaai/jina-embeddings-v3` ficou de fora pela licença (CC-BY-NC-4.0).

| Id | Modelo | Dimensões | Tamanho | Entrada máxima | Licença |
|---|---|---:|---:|---:|---|
| E0 | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (atual) | 384 | 0,22 GB | 128 tokens | Apache-2.0 |
| E1 | `sentence-transformers/paraphrase-multilingual-mpnet-base-v2` | 768 | 1,0 GB | 512 tokens | Apache-2.0 |
| E2 | `intfloat/multilingual-e5-large`, com os prefixos `query: ` e `passage: ` que o modelo exige | 1024 | 2,24 GB | 512 tokens | MIT |

## Condições iguais para todos

- Ranking padrão da #35 (A8): RRF puro sobre BM25 + busca densa só no banco vetorial, pesos 0,55/0,45, `RRF_K = 60`, sem reranker.
- `top_k = 4`, no máximo 2 Trechos por documento, síntese extrativa sem LLM, só fontes aprovadas (21 fontes de Nutrição).
- Mesmo pré-processamento do texto: o `expand_clinical_synonyms` atual (minúsculas, sem acentos, com os sinônimos clínicos), nos Trechos e na pergunta.
- Mesmo HNSW (cosseno, `ef_construction` e `ef_search` em 200). Cada modelo tem a própria coleção no ChromaDB.

## Conjuntos

- **v2** (`eval/golden/v2/`): 18 casos com recuperação no `dev` e 8 no `test`. No `dev`, um caso vale 0,056.
- **v1** (`data/benchmark/eval_questions.json`): régua do gate do CI.
- **"Não sei"** (`eval/abstencao/casos.json`): 78 casos no `dev` e 18 no `test`.

Limitação conhecida: o `test` do v2 já foi visto na #35 e não é um holdout cego. Ele serve para detectar regressão grande, não para confirmar ganho pequeno.

## Trechos não julgados

Um modelo novo pode trazer ao top-4 Trechos que o golden v2 ainda não julgou, que contam como irrelevantes. Uma primeira execução lista esses Trechos. Eles são julgados pelo conteúdo, na escala do #13 (2 responde, 1 em parte, 0 não responde), sem olhar qual modelo os trouxe, e registrados no campo `pool` dos casos, como pendentes de revisão humana. A execução final só vale com `nao_julgados = 0` em todos os candidatos.

## Limiar do "não sei" por modelo

O `ABSTENCAO_LIMIAR_COSSENO` (0,40) foi calibrado na escala de cosseno do E0. Cada modelo tem a sua escala, então o limiar é recalibrado por modelo, **só no `dev`**, com a mesma regra da #6:

- perguntas que devem ser respondidas: casos `dentro` e `grafo_sem_corpus` do `dev` de `eval/abstencao/`, e as perguntas `recuperacao` do v2 `dev` e do v1;
- limiar escolhido: o que dá o maior "não sei" fora de Nutrição no `dev` com **zero** recusas indevidas nessas perguntas; entre limiares empatados, o menor (mais longe das perguntas boas);
- o `test` só confere, com o limiar já fixado.

O segundo sinal (`TERMOS_NUTRICAO`) não muda.

## Regra de decisão

1. **Escolha pelo v2 `dev`**, com todos os Trechos do top-4 julgados:
   - métrica principal: `mrr_trecho`; desempate por `ndcg_trecho_at_k`;
   - sem queda frente a E0 em `acerto_trecho_at_k` e `acerto_completo_at_k`, nem queda maior que 5 p.p. em `cobertura_termos`; `guardrail_acuracia` igual.
2. **Conferência no v2 `test`:** o escolhido não pode cair mais que 5 p.p. frente a E0 em `mrr_trecho` nem em `acerto_trecho_at_k`.
3. **Gate do CI (v1):** sem regressão maior que 5 p.p. frente a E0 em recall@4, MRR e cobertura de termos; guardrail legal em 1,0.
4. **"Não sei"** com o limiar recalibrado, no conjunto completo: recusa indevida de no máximo 5% e "não sei" fora de Nutrição de pelo menos 85% (os mínimos do gate `[abstencao]`).
5. **Entre equivalentes** (diferença de `mrr_trecho` no `dev` menor que 0,056, uma pergunta), fica o **mais leve** (menos dimensões e menos disco).
6. Se nenhum candidato cumprir 1 a 4, o padrão continua o E0 e o resultado é registrado como negativo.

Custo, só informativo: tempo para indexar o corpus, latência da busca densa por pergunta e tamanho do modelo.

## Variante exploratória (só para o escolhido)

Para o modelo escolhido, uma variante entrega o texto **com acentos e caixa originais** (os sinônimos clínicos continuam acrescentados). Ela só substitui a configuração escolhida se cumprir a mesma regra frente a ela. Se não cumprir, fica registrada e o pré-processamento não muda.

Resultados desfavoráveis são registrados como estão.
