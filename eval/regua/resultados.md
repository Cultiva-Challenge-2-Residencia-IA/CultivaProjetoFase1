# Régua de perguntas reais (issue #118): resultados

Critérios em [`criterios.md`](criterios.md), escritos e commitados antes de medir. `gemma4:e4b` local
na RTX 5060, embeddings e reranker em CPU. Juízes: dois subagentes do Claude às cegas (lotes com nome
neutro em `juiz/`, sem a configuração), com rubrica 0/1; critério em que divergem vai a um terceiro.
Cada caso vale 3,3 p.p.

## Dev (uma medição por mudança)

| Configuração | Responde | Fiel | Tom | Não prescreve | "Não sei" nas lacunas | "Não sei" indevido | Concordância |
|---|---:|---:|---:|---:|---:|---:|---:|
| `base` (main, com o #121) | 53,3% | 80,0% | 76,7% | 93,3% | 0 de 8 | 0% | 96,7% |
| `issue120` (domínio do Trecho) | 53,3% | 80,0% | 73,3% | 93,3% | 0 de 8 | 0% | 95,0% |
| `guardrail` (busca com a pergunta da pessoa) | 50,0% | 76,7% | 73,3% | 93,3% | 0 de 8 | 5% | 96,7% |
| `filtro` (relevância em Saúde Física) | 60,0% | 86,7% | 70,0% | 96,7% | 2 de 8 | 10% | 98,3% |
| `nota` (nota curta no fim) | 60,0% | 86,7% | 70,0% | 96,7% | 2 de 8 | 10% | 97,5% |

Por tipo, no `dev`: o filtro levou "responde" em Saúde Física de 67% para 83%; a nota curta levou o
Pedido individual de 37,5% para 50%. Nutrição ficou em 33% em todas as configurações.

## Test (uma vez, na linha de base e na configuração final)

| Critério | `base` | `final` | Meta | Cumpre |
|---|---:|---:|---|---|
| 1. Responde a pergunta | 56,7% | 56,7% | +15 p.p. | **não** |
| 2. Fidelidade | 76,7% | 66,7% | não cair | **não** |
| 3. "Não sei" nas lacunas | 1 de 8 | 2 de 8 | ≥ 70% | **não** |
| 4. "Não sei" indevido nos cobertos | 0% | 15% | ≤ 10% | **não** |
| 5. Prescrição (`eval/prescricao/test.json`, com o gemma) | 1,000 / 0,938 | 1,000 / 0,938 | não cair | sim |
| Tom (sem meta) | 60,0% | 76,7% | | |
| Concordância entre juízes | 95,8% | 97,5% | | |

**A configuração final não cumpre os critérios da #118.** O ganho do `dev` (53% para 60%) não se
repetiu no `test`. A fidelidade caiu 3 casos: afirmações do grafo causal sem Trecho (tapioca para
quem tem diabetes) e relações que os Trechos não fazem (pão integral); o grafo não mudou neste PR, e
a diferença parece ser variação do gemma entre execuções. O filtro deu um "não sei" indevido numa
pergunta coberta ("o que comer antes de treinar de manhã?") e acertou 2 de 8 lacunas.

**Decisão sobre a issue (26/11/2026):** a #118 é fechada com este PR por decisão do mantenedor,
mesmo sem cumprir os critérios 1 a 4 no `test`. O trabalho restante está em "O que falta" abaixo.

**Decisão sobre o filtro de Saúde Física (26/11/2026):** fica ligado por padrão, por decisão do
mantenedor, registrando que não cumpriu o critério 4 no `test` (15% contra 10%).

## Por mudança

- **#120 (domínio do Trecho):** sem efeito na régua. Na busca de Saúde Física do `dev` da #105, com o
  reranker, acerto de 0,65 para 0,70 e MRR de 0,583 para 0,575; sem reranker e em Nutrição, idêntico
  (`eval/relevancia/resultado_busca_dev_depois120.json`; o antes foi medido no commit da linha de base).
- **Guardrail:** a busca e a síntese passaram a usar a pergunta da pessoa. Sem efeito mensurável na
  régua, e a prescrição não mudou. A troca da pergunta não era a causa principal das respostas ruins.
- **Filtro de relevância:** calibração por área no `dev` da régua (`calibracao_dev_guardrail.json`).
  Em Nutrição, o cross-encoder não separa os temas cobertos dos sem cobertura (o melhor limiar pega
  1 de 6), e o filtro segue desligado.
- **Nota curta:** o tom do `test` subiu de 60% para 76,7%.

## O que falta (depois da #118)

- **Lacunas em Nutrição:** os temas sem cobertura (sushi na gestação, ashwagandha, proteína para
  idosos) continuam recebendo Trechos sem relação. O cross-encoder não resolve; a alternativa é o LLM
  julgar se os Trechos respondem à pergunta (opção descartada na entrevista, a reavaliar).
- **Busca fora do assunto em temas cobertos** ("caminhada ou corrida para o coração" recebeu dor
  lombar), que nenhuma das mudanças tocou.
- **Grafo causal** com afirmações sem Trecho nas respostas.

## Limitações

- Juízes LLM, sem avaliação humana independente; a cobertura também foi decidida por um subagente.
- 30 casos por split; diferenças de 1 ou 2 casos estão no ruído.
- Os casos foram escritos por um subagente a partir das personas; 6 são perguntas reais da interface.
