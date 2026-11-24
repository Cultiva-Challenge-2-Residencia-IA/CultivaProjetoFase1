# Benchmark v1 de Nutrição

`eval_questions.json` tem as 16 perguntas do benchmark v1, usado hoje pelo gate do CI (`src/evaluation/run_benchmark.py`, `eval/baselines/benchmark_offline.json`). O benchmark v2, que avalia por Trecho e página, está em `eval/golden/v2/`.

| Arquivo | Conteúdo |
|---|---|
| `eval_questions.json` | Perguntas, ids esperados, palavras-chave e armadilhas de prescrição |
| `baseline_report.json` | Relatório da última execução (regravado pelo `run_benchmark.py`) |
| `benchmark_v2_report.json` | Relatório do benchmark v2 |

`eval/golden/dev/nutricao_eval_questions.json` e `eval/golden/test/nutricao_holdout_questions.json` são cópias idênticas de `eval_questions.json`: o "holdout" do v1 não é um conjunto independente.

## Como os ids esperados viram fontes

As perguntas foram escritas para o antigo `data/raw`. `mapear_esperados` (`run_benchmark.py`) converte cada id em fontes do corpus: `GUIA_MS_*` vira o Guia Alimentar (2014) inteiro, `PUBMED_<grupo>` vira os resumos do grupo, e os `DOC_*` sem procedência verificável ficam fora da média. Um id que já é fonte do corpus (`manifest.yaml`) fica como está.

## Revisão das perguntas que esperavam o `seed_guidelines` (issue #59, 21/11/2026)

Sete perguntas esperavam documentos `DOC_*` do `seed_guidelines`, que saiu do índice no PR #30. Elas foram revisadas **pelos documentos do corpus aprovado, sem olhar resultados da busca**, com a página conferida no PDF. Cada pergunta revisada tem o motivo em `expected_revision_note`.

| Pergunta | Antes | Depois |
|---|---|---|
| Q08 | Guia + `DOC_HIPERTENSAO_DASH_05` | Guia (p. 12; potássio na doença renal sem fonte aprovada) |
| Q09 | Guia + `DOC_GLICEMIA_CARBOIDRATOS_03` | Guia + ABESO (baixo índice glicêmico, p. 159) |
| Q10 | dois `DOC_*` (fora do recall) | Guia de Dietas Vegetarianas (ferro com vitamina C, p. 5 e 27; ômega-3, p. 6) |
| Q11 | dois `DOC_*` (fora do recall) | SBME (proteína para massa muscular, p. 3; suplementos proteicos e creatina, p. 6) |
| Q13 | `DOC_*` + PubMed (fora do recall) | sem fonte: o corpus não trata de curcumina |
| Q15 | Guia + `DOC_*` | sem fonte: o Guia não diz se a fervura tira benefícios do brócolis |
| Q16 | `DOC_*` + PubMed (fora do recall) | sem fonte até as diretrizes de hipertensão, pendentes, serem aprovadas |

Perguntas sem fonte esperada ficam fora da média de recall e de MRR, mas continuam valendo para palavras-chave e guardrail. As palavras-chave das sete perguntas não foram revistas: algumas ainda vêm do `seed_guidelines` (por exemplo, "HOMA-IR" e "mTORC1").

**Efeito**, com o mesmo índice e sem mudança de código: as perguntas avaliadas no recall passaram de 12 para 13 (entraram Q10 e Q11, saiu Q15). O recall@4 médio foi de 91,7% para 88,5% e o MRR de 0,778 para 0,769, porque a Q09 agora também espera a ABESO e a busca não a traz entre os 4 primeiros. Palavras-chave e guardrail ficaram iguais. O baseline do gate (`eval/baselines/benchmark_offline.json`) foi regravado com esses valores.

## Decisão: o Fascículo 1 não é equivalente ao Guia no v1

**Decisão (10/11/2026, issue #35):** nas perguntas que esperam o Guia, o v1 **não** aceita o Fascículo 1 (`protocolos-guia-alimentar-fasciculo1-2021`) como resposta equivalente. A régua do v1 não muda.

- **Proposta:** MatheusSales2773, na issue #35. **Aprovação:** grupo do projeto, sem objeções, em 10/11/2026.
- **Motivo:** a equivalência por conteúdo já é tratada no benchmark v2, que julga cada Trecho pelo que ele responde. Lá, Trechos do Fascículo recebem nota 1 ou 2 quando respondem (V2-REC-03, V2-REC-04, V2-REC-07, V2-REC-08 e V2-ADV-03). Como o v2 deve substituir o v1 no gate, mudar o mapeamento do v1 agora alteraria a régua sem ganho duradouro.
- **Efeito medido, só informativo:** com a equivalência, o MRR do v1 no ranking atual seria 0,819 em vez de 0,778 (`mrr_fasciculo_equivalente` em `eval/runs/ablacao_mrr_issue35.json`).
- **Quando revisar:** se o v1 continuar sendo o gate por muito tempo, ou se a equipe decidir que o Fascículo deve contar como fonte do Guia também fora do v2.
