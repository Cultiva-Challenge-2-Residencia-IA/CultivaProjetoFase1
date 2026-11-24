# Comparação de modelos de embeddings (issue #15): resultados e decisão

Executada em 24/11/2026. Os critérios foram registrados antes, em [`comparacao_embeddings_issue15_criterios.md`](comparacao_embeddings_issue15_criterios.md) (commit `c762bcf`). Os números completos, inclusive o RR por caso e o cosseno de cada pergunta, estão em [`comparacao_embeddings_issue15.json`](comparacao_embeddings_issue15.json).

Reproduzir:

```bash
uv run python -m src.evaluation.comparacao_embeddings                      # E0, E1 e E2
uv run python -m src.evaluation.comparacao_embeddings --modelos E2 --texto-original
```

Condições: ranking padrão da #35 (RRF puro sobre BM25 + ChromaDB), `top_k = 4`, no máximo 2 Trechos por documento, síntese extrativa sem LLM, só fontes aprovadas (21 fontes, 1.814 Trechos). Cada candidato indexa do zero, numa coleção em memória e sem o cache de vetores, num MacBook com Apple Silicon (CPU, 10 núcleos).

## Trechos julgados

A primeira execução trouxe 9 Trechos não julgados ao top-4 do v2, e a variante exploratória trouxe mais 1. Os 10 foram julgados pelo conteúdo, sem olhar qual modelo os trouxe, na escala do #13: 7 com nota 0, 2 com nota 1 e 1 com nota 2. Ficam em `eval/golden/v2/{dev,test}.json`, no campo `pool` de cada caso, como **pendentes de revisão humana**. A execução final teve `nao_julgados = 0` nos três candidatos.

| Caso | Trecho | Nota |
|---|---|---:|
| V2-ADV-03 | Guia, p. 64 (exemplos de jantar com arroz e feijão) | 1 |
| V2-REC-02 | França et al., p. 7 (recomendação de sal e óleos do Guia, edição anterior) | 1 |
| V2-REC-19 | ABESO, p. 92 (VIGITEL: 22,9% com a ingestão recomendada) | 2 |
| V2-REC-05 | Martins et al., p. 2 (variante exploratória; define em parte os processados) | 1 |
| V2-REC-04, REC-05, REC-13, REC-17 (2), REC-23 | ABESO p. 59, Monteiro p. 2, Moreira p. 4, Guia p. 42 e p. 107, SBME p. 3 | 0 |

## Resultados

### Benchmark v2 (dev para escolher, test para conferir)

| Id | Modelo | Split | Trecho@4 | Completo@4 | MRR | nDCG | Termos | Guardrail |
|---|---|---|---:|---:|---:|---:|---:|---:|
| E0 | MiniLM-L12 (atual) | dev | 0,944 | 0,722 | 0,732 | 0,466 | 0,706 | 0,889 |
| E1 | mpnet-base | dev | 0,944 | 0,778 | 0,792 | 0,459 | 0,765 | 0,889 |
| **E2** | **e5-large** | **dev** | **1,000** | **0,944** | **0,815** | **0,580** | **0,735** | **0,889** |
| E0 | MiniLM-L12 (atual) | test | 1,000 | 0,750 | 1,000 | 0,476 | 0,875 | 1,000 |
| E1 | mpnet-base | test | 1,000 | 0,750 | **0,938** | 0,477 | 0,771 | 1,000 |
| **E2** | **e5-large** | **test** | **1,000** | **0,750** | **1,000** | **0,618** | **0,875** | **1,000** |

O guardrail é igual nos três: ele não depende da busca.

RR por caso no v2 `dev`, só onde algum modelo difere do E0:

| Caso | E0 | E1 | E2 |
|---|---:|---:|---:|
| V2-ADV-04 | 0,33 | 0,50 | 0,50 |
| V2-REC-05 | 0,50 | 0,50 | 1,00 |
| V2-REC-08 | 0,25 | 0,00 | 0,50 |
| V2-REC-14 | 0,25 | 0,25 | 0,33 |
| V2-REC-17 | 0,33 | 1,00 | 0,33 |
| V2-REC-20 | 0,00 | 0,50 | 0,50 |
| V2-REC-21 (test) | 1,00 | 0,50 | 1,00 |

O E2 melhora 5 casos do `dev` e não piora nenhum frente ao E0, nem no `test`. O E1 melhora 3 casos do `dev` e piora 1 (REC-08 sai do top-4); no `test`, REC-21 cai de 1,0 para 0,5.

### Benchmark v1 (régua do gate do CI)

| Id | Recall@4 | MRR | Termos | Guardrail |
|---|---:|---:|---:|---:|
| E0 | 0,917 | 0,778 | 0,925 | 1,0 |
| E1 | 0,917 | 0,833 | 0,909 | 1,0 |
| **E2** | **1,000** | **0,840** | **0,925** | **1,0** |

No E2, Q08 sobe de 0 para 0,25 (entra no top-4) e Q14 de 0,5 para 1,0.

### "Não sei", com o limiar recalibrado por modelo no `dev`

A tabela aplica o sinal do "não sei" (cosseno abaixo do limiar e nenhum termo de Nutrição) ao cosseno de cada pergunta. Ela não conta o desvio do grafo e da TACO: quando um deles tem resultado, o sistema responde só com ele em vez de dizer "não sei" (#6). Esse desvio só reduz o "não sei", nunca cria recusa. No benchmark com o E2 já adotado, o `abstention_metrics` dá os mesmos 96% fora de Nutrição e 0 recusa indevida, mas **1/28** em Nutrição fora do corpus, contra 3/28 pelo sinal.

| Id | Limiar | Fora de Nutrição (dev / test / total) | Nutrição fora do corpus | Recusa indevida |
|---|---:|---:|---:|---:|
| E0 (limiar atual 0,40, para referência) | 0,400 | 18/21 / 5/5 / 23/26 (88%) | 1/28 | 0 |
| E0 recalibrado | 0,435 | 20/21 / 5/5 / 25/26 (96%) | 2/28 | 0 |
| E1 | 0,495 | 20/21 / 4/5 / 24/26 (92%) | 1/28 | 0 |
| **E2** | **0,845** | **20/21 / 5/5 / 25/26 (96%)** | **3/28** | **0** |

A recusa indevida conta as 89 perguntas que devem ser respondidas: os casos `dentro` e `grafo_sem_corpus` do conjunto do "não sei" e as perguntas do v1 e do v2 com comportamento `responder`. A única pergunta fora de Nutrição respondida é "Como trocar o óleo do carro?", porque "óleo" é termo do domínio.

**Folga do limiar.** No `dev`, todas as perguntas a responder têm termo de Nutrição, então a regra de calibração nunca encontra uma recusa possível: o limiar fica onde maximiza o "não sei" fora de Nutrição. Por isso vale olhar o cosseno sozinho:

| Id | Perguntas a responder abaixo do limiar (protegidas só pelo vocabulário) | Menor cosseno a responder | Maior cosseno fora de Nutrição |
|---|---:|---:|---:|
| E0 (0,435) | 9 de 89 | 0,241 | 0,432 |
| E1 (0,495) | 5 de 89 | 0,391 | 0,498 |
| E2 (0,845) | 0 de 89 | 0,846 | 0,845 |

O e5-large é o único em que o cosseno sozinho separa os dois grupos neste conjunto, mas a folga é de **0,001** dos dois lados (ABS-DEN-38 com 0,8456; ABS-FNU-11 e ABS-FNU-18 com 0,8445). O e5 comprime os cossenos numa faixa alta (mediana de 0,82 fora de Nutrição e acima de 0,87 nas perguntas a responder), e uma pergunta nova pode cair do outro lado. O vocabulário de Nutrição continua sendo a proteção contra recusa indevida.

### Custo (informativo)

| Id | Dimensões | Modelo em disco | Indexar 1.814 Trechos | Busca densa por pergunta (mediana / p95) |
|---|---:|---:|---:|---:|
| E0 | 384 | 0,22 GB | 30 s | 5 / 12 ms |
| E1 | 768 | 1,0 GB | 3,5 min | 9 / 16 ms |
| E2 | 1024 | 2,24 GB | **19 min** | 28 / 47 ms |

## Decisão

Pela regra registrada antes da execução:

1. **v2 `dev`:** o E2 tem o maior MRR (0,815) e não cai em nada frente ao E0: o acerto de Trecho vai de 0,944 a 1,000, o completo de 0,722 a 0,944 e a cobertura de termos sobe 2,9 p.p. O E1 também cumpre essa etapa (0,792).
2. **Conferência no `test`:** o E2 mantém o MRR em 1,000. O **E1 cai 6,25 p.p.** (1,000 para 0,938), acima do limite de 5 p.p., e sai. Sem essa regra, E1 e E2 seriam equivalentes no `dev` (diferença de 0,023, menos de uma pergunta) e a regra 5 escolheria o E1, mais leve.
3. **Gate do v1:** o E2 melhora recall e MRR, com termos e guardrail iguais.
4. **"Não sei":** recusa indevida 0 e 96% fora de Nutrição, acima dos mínimos do gate (5% e 85%).
5. O E2 está a mais de uma pergunta do E0 (0,083 contra 0,056).

**Escolhido: E2, `intfloat/multilingual-e5-large`**, com os prefixos `query: ` e `passage: `, e o `ABSTENCAO_LIMIAR_COSSENO` em 0,845. A justificativa não depende só da métrica: o E0 trunca cada Trecho em 128 tokens, perto da metade do texto, e o e5 lê até 512.

**Variante exploratória** (E2 com acentos e caixa originais): MRR do `dev` 0,773 e acerto completo 0,889, abaixo do E2 normalizado. Não cumpre a regra frente a ele, e o pré-processamento não muda (`EMBEDDING_NORMALIZAR_TEXTO=true`). O Trecho que ela trouxe sem julgamento (REC-05, nota 1) foi julgado depois e não muda o resultado: o RR desse caso já era 1,0, e a nota 1 não conta no acerto completo.

O provedor e o custo estão no [ADR 0005](../../docs/adrs/0005-provedor-embeddings.md). Para o custo da indexação, entrou um cache de vetores por modelo e texto (`EMBEDDING_CACHE_PATH`): só Trechos novos ou alterados são recalculados, e o CI guarda o cache e o modelo com `actions/cache`.

## Resultados desfavoráveis e limitações

- **Indexar fica cerca de 38 vezes mais lento** (30 s para 19 min sem cache) e a busca densa 5 vezes (5 ms para 28 ms). A primeira execução numa máquina nova, ou no CI sem cache, paga a indexação inteira, e o corpus com as fontes pendentes tem mais Trechos.
- **A folga do limiar do "não sei" é de 0,001** (seção acima). O limiar é frágil a perguntas novas, e o gate `[abstencao]` pode oscilar com mudanças pequenas no corpus.
- **Amostra pequena:** são 18 casos no `dev` e 8 no `test` do v2, e o `test` já tinha sido visto na #35. O ganho é consistente (nenhum caso piora), mas não foi confirmado num conjunto cego.
- **Julgamento por IA:** os 10 Trechos novos foram julgados por `rascunho-claude`, a mesma origem do pool da #35, com revisão humana pendente. Quem julgou também montou o script.
- **A cobertura de termos do `test` cai no E1** (0,875 para 0,771). Isso não conta para a decisão, mas reforça a exclusão do E1.
