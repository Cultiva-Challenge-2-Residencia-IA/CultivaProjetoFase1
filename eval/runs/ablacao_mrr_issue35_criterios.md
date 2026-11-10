# Ablação do ranking — critérios definidos antes da execução (issue #35)

Registrado em 10/11/2026, antes de rodar qualquer variante.

## Pergunta

Por que a fonte esperada nem sempre aparece em 1º lugar (MRR 0,750), e alguma das três hipóteses da issue explica a queda?

## Conjunto e limitações conhecidas antes da execução

- Golden set: `data/benchmark/eval_questions.json` (16 perguntas; 12 com fonte esperada no corpus aprovado).
- As 12 perguntas avaliadas esperam a **mesma fonte**: o Guia Alimentar (2014). O MRR mede, na prática, se o Guia vem em 1º lugar. Um ajuste que favoreça o Guia melhora a métrica sem demonstrar melhora da busca.
- `eval/golden/test/nutricao_holdout_questions.json` é idêntico byte a byte ao conjunto de desenvolvimento. **Não há conjunto independente**: todo resultado aqui é medido dentro da amostra usada para escolher a variante.
- Por isso, nenhum resultado desta ablação é tratado como evidência de melhora geral. Ganhos são **hipóteses** a confirmar em um conjunto novo (#13).

## Variantes (fixadas antes da execução)

| Id | Variante | Hipótese da issue |
|---|---|---|
| A0 | Configuração atual (RRF 0,55/0,45; sobreposição 0,25; bônus de evidência) | referência |
| A1 | Sem bônus de evidência | H1 |
| A2 | Sem sobreposição de termos | H1 |
| A3 | Sem bônus e sem sobreposição (RRF puro) | H1 |
| A4 | RRF com pesos iguais (0,5/0,5) | pesos do RRF |
| A5 | Só BM25 | pesos do RRF |
| A6 | Só a busca densa | pesos do RRF |
| A7 | Busca densa só com ChromaDB (sem TF-IDF/LSA) | H3 |
| A8 | A7 sem bônus e sem sobreposição | H1 + H3 |

Todas usam o mesmo índice, as mesmas 16 perguntas, `top_k = 4`, no máximo 2 Trechos por documento, síntese extrativa sem LLM e só fontes aprovadas.

## Métricas

- Recall@4, MRR, cobertura de palavras-chave e acurácia do guardrail, gerais e por categoria, com a mesma régua do `run_benchmark.py`.
- **MRR alternativo (H2)**, apenas informativo: aceita o Fascículo 1 como equivalente ao Guia. Ele **não substitui** a régua oficial; mudar a régua é decisão da equipe.
- RR por pergunta, para mostrar quais perguntas mudam.

## Critério para uma variante ser candidata

Todos ao mesmo tempo, contra A0:

1. MRR oficial > 0,750;
2. Recall@4 ≥ 0,9167;
3. Guardrail legal = 1,0;
4. Cobertura de palavras-chave sem queda maior que 5 p.p.

Ser candidata não basta para virar padrão: a mudança precisa ter justificativa independente da métrica (não pode ser só "favorece o Guia"), e a decisão fica registrada como proposta técnica até haver conjunto independente.

Resultados desfavoráveis (nenhuma variante candidata, ou ganho só no MRR alternativo) são registrados como estão.
