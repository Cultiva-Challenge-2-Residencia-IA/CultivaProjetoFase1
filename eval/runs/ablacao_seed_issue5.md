# Ablação do `seed_guidelines` (issue #5): resultados

Executado em 17/11/2026 com `uv run python -m src.evaluation.ablacao_seed`, depois de registrar os critérios em [`ablacao_seed_issue5_criterios.md`](ablacao_seed_issue5_criterios.md). Dados completos em [`ablacao_seed_issue5.json`](ablacao_seed_issue5.json).

**Configuração:**
- sem LLM (síntese extrativa), com os parâmetros padrão de `src/config.py` e k = 4;
- **S0** são as fontes aprovadas (índice atual); **S1** é S0 com os 19 Trechos dos 10 documentos do `seed`;
- duas execuções seguidas geraram JSONs idênticos;
- S0 E3 reproduz exatamente o `data/benchmark/baseline_report.json` atual.

## Resultado em uma frase

**Devolver o `seed` ao índice não melhora a busca e piora o ranking.** O MRR do v1 cai de 0,7778 para 0,7083, e o MRR por Trecho do v2 cai no dev e no test. O v1, porém, foi escrito em função do `seed`: as 7 perguntas que esperam `DOC_*` o encontram no top-4.

## v1, régua comum

Mesmos grupos esperados nas duas condições (os `DOC_*` continuam descartados).

| Condição | Estágio | recall@4 | MRR | Cobertura de palavras-chave | Guardrail | Posições do top-4 com `seed` |
|---|---|---:|---:|---:|---:|---:|
| S0 | E1 só RAG | 0,9167 | 0,7778 | 0,4427 | 1,0000 | 0% |
| S0 | E2 + TACO | 0,9167 | 0,7778 | 0,4927 | 1,0000 | 0% |
| S0 | **E3 + TACO + grafo** | **0,9167** | **0,7778** | **0,9250** | 1,0000 | 0% |
| S1 | E1 só RAG | 0,9167 | 0,7083 | 0,6458 | 1,0000 | 18,75% |
| S1 | E2 + TACO | 0,9167 | 0,7083 | 0,6958 | 1,0000 | 18,75% |
| S1 | **E3 + TACO + grafo** | **0,9167** | **0,7083** | **0,9250** | 1,0000 | 18,75% |

**Perguntas cujo MRR muda no E3** (o `seed` entra acima da fonte do corpus):

| Pergunta | RR em S0 | RR em S1 | Top-4 em S1 |
|---|---:|---:|---|
| Q07_MULTIHOP_GAP | 1,0 | 0,5 | `DOC_BIOATIVOS_…_08`, Guia, `DOC_BIOATIVOS_…_08`, Guia |
| Q09_LEGAL_TRAP | 0,5 | 0,25 | `DOC_GLICEMIA_…_03` (2×), Fascículo 1, Guia |
| Q15_NATURAL_GRAPH | 0,333 | 0,25 | `DOC_BIOATIVOS_…_08`, SVB (2×), Guia |

**Cobertura de palavras-chave sem o grafo:** no E1, o `seed` sobe a cobertura em 20 p.p. (0,44 → 0,65), nas perguntas Q07, Q09, Q11, Q13 e Q15. No E3, a cobertura fica igual (0,925), porque o grafo causal já traz esses termos.

## v2 (Trecho e página esperados), configuração da entrega (E3)

| Split | Condição | acerto do Trecho @4 | MRR do Trecho | nDCG @4 | Cobertura de termos | Guardrail |
|---|---|---:|---:|---:|---:|---:|
| dev | S0 | 0,9444 | **0,7315** | 0,4657 | 0,7059 | 0,8889 |
| dev | S1 | 0,9444 | **0,6991** | 0,4489 | 0,7059 | 0,8889 |
| test | S0 | 1,0000 | **1,0000** | 0,4758 | 0,8750 | 1,0000 |
| test | S1 | 1,0000 | **0,9375** | 0,4343 | 0,8750 | 1,0000 |

Os Trechos do `seed` ocupam 14 de 156 posições do top-4 (9%), em 13 das 42 perguntas. O RR muda em V2-GRA-01 (1,0 → 0,5), V2-REC-12 (1,0 → 0,5) e V2-ADV-04 (0,333 → 0,25). Não apareceram Trechos do corpus não julgados em nenhuma condição.

## Hipóteses, pela regra registrada antes

| Hipótese | Regra | Resultado |
|---|---|---|
| **H1:** a qualidade atual não depende do `seed` | No E3, diferença entre S1 e S0 de no máximo 5 p.p. (ou 0,05 de MRR) em recall@4, MRR e cobertura | **Não sustentada pela regra escrita:** o MRR difere em 0,0695. Recall@4 e cobertura não mudam. A diferença vai no sentido contrário ao de uma dependência: com o `seed`, o MRR **piora**. Limitação dos critérios, percebida só depois de medir: a regra deveria ter sido unilateral (só uma piora sem o `seed` indicaria dependência). Não mudamos a regra; registramos aqui. |
| **H2:** o `seed` desloca Trechos do corpus | `acerto_trecho_at_k` ou `mrr_trecho` do v2 cai em S1 em algum split | **Sustentada:** o MRR do Trecho cai 0,032 no dev e 0,0625 no test; o acerto @4 não muda |
| **H3:** o v1 foi escrito em função do `seed` | Algum `DOC_*` esperado no top-4 em pelo menos 4 das 7 perguntas que o esperam | **Sustentada:** 7 de 7 |

## Conclusão: o que permanece no baseline

1. **O `seed_guidelines` continua fora do índice.** Esta era a decisão do PR #30, por falta de procedência (RF-IA01, RN17). A ablação mostra que ela também não custa qualidade de busca: recall@4 e cobertura na configuração da entrega são iguais, e o ranking fica melhor sem o `seed`.
2. **O baseline atual (S0 E3) permanece como está:** recall@4 0,9167, MRR 0,7778, cobertura 0,925, guardrail 1,0. Nenhuma mudança em `eval/baselines/benchmark_offline.json`.
3. **O v1 ainda carrega o `seed` nas perguntas.**
   - Sete das 16 perguntas esperam `DOC_*`, e duas (Q10 e Q11) só esperavam `DOC_*`; elas não entram no recall de hoje.
   - Pela regra registrada, a recomendação é **revisar os ids esperados dessas perguntas ou passar o gate para o v2** (issue #13), e não reintroduzir o `seed`.
4. **A queda do MRR de 0,9688 (05/11) para 0,7778 não vem da saída do `seed`.** Com a mesma régua, tirar o `seed` aumenta o MRR. A queda vem da troca de base (`data/raw`, com o Guia por capítulo, para o corpus aprovado) e do mapeamento dos ids, como já apontava o comentário de 08/11 na issue. `eval/runs/latest_ablation_report.json` fica como registro histórico dessa base antiga.

## Observação fora do escopo

Sem o grafo (E1), a cobertura de palavras-chave do v1 é 0,44; com o grafo (E3), 0,925. Quase toda a cobertura do v1 vem, portanto, do texto do grafo causal (`data/raw/knowledge_graph`), e não dos Trechos. A procedência das 14 cadeias do grafo estava no escopo da issue #3 (auditoria de procedência), encerrada em 05/11/2026 sem esse critério cumprido, por decisão registrada na #5. Esta ablação não reabre a #3; o número só mostra o quanto o v1 depende do grafo.
