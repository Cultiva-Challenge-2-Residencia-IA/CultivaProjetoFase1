# Relatório: respostas com RAG e sem RAG

**CULTIVA — avaliação comparativa de respostas**
**Data:** 17 de novembro de 2026
**Escopo:** comparação entre o modelo respondendo sem contexto recuperado e o mesmo fluxo com recuperação RAG.

## Resumo executivo

O experimento quer responder a uma pergunta simples: **dar ao modelo trechos recuperados pelo RAG melhora as respostas?** Para isolar esse efeito, as duas condições precisam usar o mesmo modelo, instruções e configurações; a única diferença deve ser a presença dos trechos recuperados.

Os arquivos disponíveis trazem dois resultados, que não devem ser misturados:

1. O relatório mais recente usa o split `test` (6 casos), mas foi executado com `--no-llm`. Portanto, a condição chamada `llm_sem_rag` não representa uma LLM real nessa execução; as respostas usam o modo extrativo do projeto.
2. Há um relatório anterior identificado como Ollama, no split `dev` (7 casos). É o resultado existente mais próximo da comparação com LLM, mas os artefatos não guardam o nome exato do modelo, a versão, a configuração de geração ou a revisão do código usada.

**Conclusão:** os resultados são exploratórios. O relatório recente não mede LLM-only; o relatório Ollama sugere melhora com RAG nesta pequena amostra de desenvolvimento, mas não basta para afirmar ganho generalizável.

## 1. O que está sendo comparado

| Condição | O que recebe | O que ajuda a investigar |
|---|---|---|
| **Sem RAG** (`llm_sem_rag`) | Pergunta e instruções, sem trechos recuperados | O que o modelo consegue responder sem consultar o corpus. |
| **Com RAG** (`rag_atual`) | Pergunta, trechos recuperados e o fluxo atual do consultor | Se a recuperação e o uso das evidências melhoram a resposta final. |
| **Oracle** (`contexto_oracle`) | Pergunta e trechos de referência definidos no caso | Diagnóstico adicional: estima como o fluxo se comporta quando recebe aqueles trechos diretamente. Não é uma resposta perfeita nem isola sozinho o retriever. |

Para uma comparação justa entre as duas primeiras condições, use o mesmo modelo, prompt, temperatura, versão do código e conjunto de perguntas. O modo de geração precisa estar registrado em cada relatório.

## 2. Resultados disponíveis

### 2.1 Execução mais recente: split `test`, modo extrativo

Fonte: `data/benchmark/relatorio_respostas_test_extrativo_20261117.json`. Foram avaliadas 6 perguntas em cada condição. O runner foi chamado com `--no-llm`; estes números **não são uma medição de LLM-only versus LLM+RAG**.

| Métrica | Sem RAG (extrativo) | Com RAG (extrativo) | Diferença com RAG |
|---|---:|---:|---:|
| Nota geral ponderada | 0,548 | 0,712 | +0,164 |
| Completude | 0,000 | 0,278 | +0,278 |
| Relevância lexical | 0,440 | 0,638 | +0,198 |
| Segurança/ressalvas | 0,667 | 0,917 | +0,250 |
| Correção factual (detector atual) | 1,000 | 1,000 | 0,000 |
| Fidelidade ao contexto | N/A | 0,608 | — |
| Validade de citações (heurística atual) | N/A | 1,000 | — |
| Abstenção adequada | 0,500 | 0,833 | +0,333 |

Há 6 casos, então cada caso representa 16,7 pontos percentuais em taxas simples. Além disso, o split `test` está identificado como holdout e tem revisão humana pendente; use-o para medir, não para ajustar as regras.

### 2.2 Relatório existente identificado como Ollama: split `dev`

Fonte: `data/benchmark/relatorio_respostas_comparativo_ollama.json` e `eval/runs/respostas/relatorio_respostas_comparativo_ollama.md`. São 7 casos de desenvolvimento. O nome do arquivo identifica a execução como Ollama, mas os artefatos não registram o modelo ou os parâmetros exatos.

| Métrica | Sem RAG (Ollama) | Com RAG (Ollama) | Diferença com RAG |
|---|---:|---:|---:|
| Nota geral ponderada | 0,554 | 0,700 | +0,146 |
| Completude | 0,000 | 0,220 | +0,220 |
| Relevância lexical | 0,420 | 0,657 | +0,237 |
| Segurança/ressalvas | 0,714 | 0,929 | +0,215 |
| Correção factual (detector atual) | 1,000 | 1,000 | 0,000 |
| Fidelidade ao contexto | N/A | 0,304 | — |
| Validade de citações (heurística atual) | N/A | 0,857 | — |
| Abstenção adequada | 0,571 | 0,857 | +0,286 |

No confronto pareado registrado, RAG venceu em 5 dos 7 casos e empatou em 2. Isso descreve somente esse conjunto pequeno de desenvolvimento; não é evidência estatística de ganho em novos casos.

## 3. Como as métricas atuais são calculadas

As regras estão em `src/evaluation/benchmark_respostas.py`. As notas individuais vão de 0 a 1; o relatório apresenta médias entre casos.

| Métrica | Medição implementada | Como interpretar e limite atual |
|---|---|---|
| **Completude** | Cada fato essencial tem um peso. O fato é contado como atendido se pelo menos 45% das palavras normalizadas com mais de 4 caracteres aparecem na resposta. A nota é a soma dos pesos atendidos dividida pela soma dos pesos. | Aproxima cobertura do gabarito, mas correspondência lexical pode perder paráfrases ou aceitar frases que usam as mesmas palavras sem expressar o fato. |
| **Correção factual** | Começa em 1,0. O avaliador procura frases proibidas; se pelo menos 75% das palavras relevantes de uma proibição aparecerem, aplica penalidade conforme a gravidade. | Não confere todos os fatos positivos contra fontes. Uma nota 1,0 significa “nenhuma proibição detectada por essa regra”, não “resposta comprovadamente correta”. |
| **Relevância** | Calcula a proporção de palavras da pergunta (mais de 3 caracteres) encontradas na resposta e usa `0,4 + 0,6 × proporção`, limitada a 0,4–1,0. | É uma estimativa lexical. Repetir termos da pergunta pode elevar a nota sem responder bem; uma boa paráfrase pode reduzi-la. |
| **Segurança/ressalvas** | Regras específicas para pedidos de prescrição e para casos em que se espera abstenção. Para os demais casos, a nota parte de 1,0. | É um cheque parcial de comportamento, não uma avaliação clínica abrangente. A taxa de abstenção adequada é reportada separadamente. |
| **Fidelidade ao contexto** | Nos casos com contexto, mede a proporção de palavras da resposta com mais de 4 caracteres que também aparecem no contexto, multiplicada por 1,5 e limitada a 1,0. | Mede sobreposição de vocabulário, não se o contexto sustenta semanticamente cada afirmação. |
| **Validade de citações** | Sem RAG é N/A. Com RAG, se existe ao menos uma citação, a nota atual é 1,0; sem citação, RAG recebe 0,5. | A implementação não valida que a citação aponta para um trecho recuperado ou que esse trecho apoia a frase citada. |
| **Abstenção adequada** | Detecta certas frases como “não sei”, “fora de escopo” ou “não há evidência”, conforme o comportamento esperado. A média é a taxa de casos marcados como adequados. | Um conjunto fixo de expressões pode não reconhecer formulações equivalentes e pode confundir menções com uma abstenção real. |
| **Nota geral ponderada** | `0,35 × correção + 0,30 × completude + 0,15 × relevância + 0,20 × segurança`. Com erros proibidos detectados, a nota fica limitada a 0,4. | Fidelidade, citações e abstenção não entram diretamente na nota geral. A nota herda as limitações das quatro medidas incluídas. |

**Analogia de mentor:** pense em uma prova com gabarito. A completude verifica se certos tópicos aparecem; a relevância verifica se o texto repete termos do enunciado; a segurança procura algumas respostas proibidas. Isso é útil como triagem automática, mas ainda não equivale a um professor conferindo se o raciocínio está correto e se as fontes realmente o sustentam.

## 4. Métricas de recuperação são outra etapa

O benchmark `eval/golden/v2/` avalia a lista de trechos recuperados antes da geração. Ele usa julgamentos de relevância por trecho (0 = não responde, 1 = parcial, 2 = completo), especialmente:

| Métrica de recuperação | Leitura simples |
|---|---|
| **Recall de trecho@k** | Quantos trechos relevantes esperados apareceram entre os primeiros k. |
| **MRR** | Quão cedo apareceu o primeiro trecho relevante; posição 1 vale 1, posição 2 vale 0,5. |
| **nDCG** | Se os trechos mais completos foram colocados antes dos parciais e irrelevantes. |
| **Acerto de página/fonte** | Se ao menos uma página ou fonte esperada foi alcançada. |

Essas métricas ajudam a dizer se a busca encontrou e ordenou bem a evidência. Não medem, por si só, se o modelo escreveu uma boa resposta. O relatório comparativo de respostas, por sua vez, avalia a resposta final e não substitui o benchmark de recuperação.

## 5. Como melhorar a avaliação

| Prioridade | Melhoria | Benefício esperado |
|---|---|---|
| **1 — validade do experimento** | Executar sem RAG e com RAG usando exatamente o mesmo LLM e configurações; registrar provedor, nome/versão do modelo, parâmetros, prompt, commit e split no relatório. | Torna possível atribuir diferenças à presença do RAG e reproduzir a execução. |
| **2 — gabarito independente** | Revisar os fatos e os casos por avaliadores que não ajustaram o sistema; manter `test` congelado e ampliar o número de casos. | Reduz viés e a instabilidade causada por amostras pequenas. |
| **3 — correção factual real** | Avaliar afirmações atômicas como apoiadas, contraditas ou sem evidência, conferindo-as contra fontes. Usar revisão humana em amostra e adjudicação de divergências. | Distingue resposta correta de resposta que apenas não acionou um detector lexical. |
| **4 — completude semântica** | Aceitar paráfrases; combinar juiz humano ou avaliador semântico calibrado com regras automáticas. Medir acordo do avaliador automático com pessoas. | Evita que palavras diferentes sejam confundidas com fatos ausentes. |
| **5 — citações e fundamentação** | Extrair as afirmações com citação e verificar se o `doc_id` foi recuperado e se o trecho sustenta a afirmação específica. | Mede rastreabilidade, em vez de mera presença de uma citação. |
| **6 — análise estatística** | Reportar resultados por caso, diferenças pareadas, tamanho do efeito e intervalos de confiança; repetir a execução quando o modelo for não determinístico. | Mostra a incerteza e evita tratar pequenas diferenças como conclusivas. |
| **7 — busca** | Continuar medindo Recall@k, MRR e nDCG; reportar também precisão@k e resultados por tipo de pergunta. | Separa problemas de recuperação de problemas de geração. |

## 6. Recomendação e conclusão

O próximo resultado a produzir deve ser uma comparação pareada no split apropriado, com LLM disponível, mesmo modelo e configurações, e metadados completos. A execução extrativa recente serve como teste do fluxo e das heurísticas; não demonstra o que uma LLM isolada faria. O relatório existente marcado como Ollama é um indício preliminar de ganho em `dev`, mas precisa de melhor rastreabilidade e de validação em casos revisados e independentes.

**Em resumo:** RAG pode ajudar o modelo a fundamentar respostas, mas a avaliação atual ainda mede vários aspectos por palavras-chave. Primeiro é preciso garantir que a comparação realmente usou o mesmo LLM; depois, melhorar a avaliação semântica de fatos, citações e suporte nas fontes.

### Artefatos consultados

- `data/benchmark/relatorio_respostas_test_extrativo_20261117.json`
- `data/benchmark/relatorio_respostas_comparativo_ollama.json`
- `eval/runs/respostas/relatorio_respostas_comparativo_ollama.md`
- `src/evaluation/benchmark_respostas.py`
- `src/evaluation/benchmark_v2.py`
- `eval/golden/resposta/README.md`
- `eval/golden/v2/README.md`
