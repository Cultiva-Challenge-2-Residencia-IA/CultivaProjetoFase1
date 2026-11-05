# Rubrica de Avaliação Científica e Ético-Legal (`nutri-evidence-consultant`)

A avaliação automatizada em [`src/evaluation/run_benchmark.py`](../../src/evaluation/run_benchmark.py) mede 4 dimensões quantitativas sobre as 16 questões do conjunto Golden (`data/benchmark/eval_questions.json` e `eval/golden/dev/`):

| Métrica | Fórmula / Critério | Meta Mínima | Resultado Alcançado (Passo 3) |
| :--- | :--- | :---: | :---: |
| **1. Document Recall@4** | Proporção dos documentos-fonte esperados recuperados nos 4 primeiros chunks do RAG Híbrido | $\ge 80.0\%$ | **`93.8%`** |
| **2. Cobertura Geral de Conceitos** | Proporção de biomarcadores, compostos, valores TACO e mecanismos esperados presentes na resposta final | $\ge 75.0\%$ | **`86.8%`** |
| **3. Cobertura Multi-Hop / TACO / Grafo** | Desempenho específico nas questões que exigem cálculo na TACO ou travessia de 4 camadas no Grafo (`Q06`-`Q08`, `Q13`-`Q16`) | $\ge 80.0\%$ | **`90.5%`** |
| **4. Precisão do Guardrail Legal** | Taxa de acerto na ativação/não-ativação da trava da Lei Federal nº 8.234/91 | `100.0%` | **`100.0%` (16/16)** |
