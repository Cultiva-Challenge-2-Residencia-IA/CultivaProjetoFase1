# Ablação do `seed_guidelines` (issue #5): critérios definidos antes da execução

Registrado em 17/11/2026, antes de rodar `src/evaluation/ablacao_seed.py`.

## Pergunta

Quanto da qualidade medida da busca e da resposta vem das 10 "sínteses normativas" de `data/raw/guidelines/seed_guidelines.json`, que não têm procedência verificável e saíram do índice no PR #30?

Os Trechos do `seed` se apresentam como "Ministério da Saúde (Brasil)", com nível de evidência de diretriz (`GUIDELINE_CONSENSUS`), sem origem registrada.

## Por que não comparar com a ablação de 05/11

`eval/runs/latest_ablation_report.json` (MRR 0,9688) foi medido sobre o `data/raw` (47 documentos, Guia por capítulo e o `seed`), com outra régua de ids esperados. A queda para o MRR atual mistura a troca de base, o mapeamento dos ids e a saída do `seed`. Esta ablação isola só o `seed`: **mesmo código, mesmo corpus aprovado, mesmas perguntas e mesmos parâmetros**, com e sem os Trechos do `seed`.

## Condições

| Condição | Índice |
|---|---|
| **S0** (atual) | Trechos das fontes aprovadas (`corpus_loader`, gate de aprovação) |
| **S1** | S0 + os Trechos do `seed_guidelines` (`ContextualChunker`, como no modo legado) |

Cada condição roda nos três estágios da ablação original: **E1** só RAG; **E2** RAG + TACO; **E3** RAG + TACO + grafo (configuração da entrega). Tudo sem LLM (`enable_ollama=False`, síntese extrativa), com os parâmetros padrão de `src/config.py`.

## Métricas

1. **v1, régua comum** (`data/benchmark/eval_questions.json`, a régua do gate): recall@4, MRR, cobertura de palavras-chave e guardrail legal. Nas duas condições, os ids `DOC_*` continuam descartados por `mapear_esperados`, então as duas usam exatamente os mesmos grupos esperados.
2. **v1, régua antiga** (só S1, informativo): em quantas das 7 perguntas que esperam `DOC_*` algum desses documentos aparece no top-4. Mostra quanto o v1 foi escrito em função do `seed`.
3. **Presença do `seed`** (só S1): fração das posições do top-4 ocupadas por Trechos `DOC_*`, no v1 e no v2.
4. **v2** (`eval/golden/v2/`, Trecho e página esperados): `acerto_trecho_at_k`, `mrr_trecho`, `ndcg_trecho_at_k`, `cobertura_termos` e `guardrail_acuracia`, por split. Um Trecho do `seed` no top-k conta como irrelevante, porque não é fonte aceitável; mudanças no v2 entre S0 e S1 medem o **deslocamento** de Trechos do corpus.

O split `test` do v2 só mede: nenhuma decisão desta issue ajusta nada a partir dele.

## Hipóteses e regra de leitura

- **H1:** a qualidade do sistema atual não depende do `seed`. Fica sustentada se, no E3, a diferença entre S1 e S0 na régua comum do v1 for **≤ 5 p.p.** (ou 0,05 de MRR) em recall@4, MRR e cobertura de palavras-chave. Diferenças maiores são relatadas como dependência, com as perguntas responsáveis.
- **H2:** o `seed` desloca Trechos do corpus. Fica sustentada se o `acerto_trecho_at_k` ou o `mrr_trecho` do v2 cair em S1 em relação a S0, em algum split.
- **H3:** o v1 foi escrito em função do `seed`. Fica sustentada se, em S1, algum `DOC_*` esperado aparecer no top-4 em pelo menos 4 das 7 perguntas que o esperam.

Todos os resultados são relatados, inclusive os desfavoráveis.

## O que já está decidido, independentemente do resultado

O `seed_guidelines` **não volta ao índice**: sem procedência verificável, ele não pode ser citado como fonte (RF-IA01, RN17), e a saída foi decidida no PR #30. A ablação mede o custo dessa decisão e se o benchmark v1 ainda depende dele.

- Se H1 falhar ou H3 for sustentada, a recomendação é revisar os ids esperados e as palavras-chave das perguntas afetadas do v1 ou passar o gate para o v2 (issue #13), e não reintroduzir o `seed`.
- Se H2 for sustentada, ela reforça a saída: além de não ter procedência, o `seed` tira espaço de Trechos com procedência.
