# Relevância da busca (issue #105): critérios definidos antes da medição

Registrado em 24/11/2026, antes de rodar a busca com qualquer caso novo e antes de mudar o código. Os casos novos (`busca_saude_fisica.json`, `sem_base.json` e `roteamento.json`) foram escritos pelo autor do código. As fontes esperadas e a ausência de base foram conferidas pela busca de termos no texto dos Trechos, e não pelo resultado da busca. O autor ser o mesmo é uma limitação, registrada em cada resultado. Os casos da #99 (`eval/multiagentes/`) já foram vistos e entram só como verificação de regressão.

`dev` serve para escolher e calibrar. O `test` roda uma vez, depois de todas as decisões, e só mede.

## Conjuntos

| Conjunto | Casos | Uso |
|---|---|---|
| Golden novo de Saúde Física (`busca_saude_fisica.json`) | 20 `dev`, 12 `test` | Busca por fonte (acerto@4 e MRR da primeira fonte esperada) e controle com base do filtro |
| Golden v2 de Nutrição, casos `responder` com Trechos julgados | `dev` e `test` | Busca por Trecho (MRR e recall@4 de `benchmark_v2.metricas_de_recuperacao`) e controle com base |
| "Não sei", tipo `dentro` (`eval/abstencao/casos.json`) | 34 `dev`, 7 `test` | Controle com base do filtro em Nutrição |
| Sem base (`sem_base.json`) | 14 `dev`, 6 `test` | Pergunta da área sem base nas fontes: o esperado é a lacuna |
| Roteamento novo (`roteamento.json`) | 18 `dev`, 8 `test` | Vocabulário de roteamento |

## 1. Reranker cross-encoder

- **Configurações, no mesmo índice:** a busca híbrida atual (base) e a busca híbrida com reranker. O reranker reordena os 20 primeiros candidatos da fusão, e depois vale o limite de Trechos por documento. Há dois candidatos multilíngues, locais pelo fastembed: `BAAI/bge-reranker-v2-m3` e `jinaai/jina-reranker-v2-base-multilingual`.
- **Regra de decisão (`dev`):**
  - em Saúde Física, o reranker é aceito se o MRR da fonte subir ao menos 0,05 sobre a base;
  - em Nutrição, ele só fica ligado se o MRR e o recall@4 não ficarem menores que os da base. Se piorar, o reranker fica ligado só em Saúde Física;
  - entre os modelos aceitos, fica o de maior MRR em Saúde Física. Se a diferença for menor que 0,02, fica o de menor latência;
  - se nenhum modelo for aceito, o reranker fica desligado.
- A latência do reranker por pergunta (mediana e p95, nesta máquina, em CPU) é relatada, mas não decide.

## 2. Filtro de relevância antes da síntese

- **Nota:** a nota de relevância de cada Trecho é a do cross-encoder escolhido em 1 (sigmoide da saída) para o par (pergunta, Trecho). Se nenhum reranker for aceito, o filtro usa o `bge-reranker-v2-m3`.
- **Decisão:** Trechos com nota abaixo de τ não vão para a síntese. Se nenhum Trecho passar, a pergunta tem lacuna. Com o LLM, a busca é reformulada antes (seção 3). Sem nenhum Trecho, a resposta é a lacuna explícita, com o que a área cobre, sem Trechos.
- **Calibração de τ (`dev`, sem LLM):** o maior τ com lacuna indevida de no máximo 5% nos controles com base do `dev`, juntos: golden novo de Saúde Física, golden v2 de Nutrição e "não sei" do tipo `dentro`.
- **Critérios, sem LLM, no `dev` e no `test`:**
  - lacuna em pelo menos 75% dos casos sem base;
  - lacuna indevida de no máximo 5% nos controles com base;
  - recall@4 de Nutrição depois do filtro (o Trecho julgado que sobra) no máximo 0,05 abaixo do recall sem filtro.
- O gate `[abstencao]` do CI continua valendo: no máximo 5% de recusa indevida.

## 3. Reformulação da busca (com o LLM)

- Quando nenhum Trecho passa no filtro, uma chamada ao LLM local reformula a pergunta: termos técnicos e, em Saúde Física, a versão em inglês, a língua de 16 das 18 fontes. A busca roda de novo e o filtro julga outra vez.
- **Métricas (`dev`):** fração dos controles com base que estavam em lacuna e saem dela (resgate) e fração dos casos sem base que continuam em lacuna.
- **Regra:** a reformulação fica ligada se a lacuna nos casos sem base continuar em pelo menos 75%. Se cair abaixo, ela fica desligada.

## 4. Trecho hipotético (HyDE) só em Saúde Física (com o LLM)

- **Comparação pareada:** a melhor busca de 1 sem e com o trecho hipotético da reescrita (`src/orquestrador/reescrita.py`), fundidos por RRF, no golden novo de Saúde Física.
- **Regra (`dev`):** o HyDE liga por padrão só no Agente de Saúde Física se o MRR da fonte subir ao menos 0,05. Em Nutrição, ele continua desligado (decisão da #99).

## 5. Vocabulário de roteamento

- **Critério:** com só as regras (o que o CI mede), acerto de pelo menos 0,90 nos casos `clara` do roteamento novo, no `dev` e no `test`.
- **Regressão:** o acerto só com regras nos casos da #99 (`eval/multiagentes/roteamento.json` e `compostas.json`, todos os splits) não pode cair. C13 e R37, os erros da #99, são relatados à parte, sem servir de critério, porque já foram vistos.

## Configuração medida

As medidas sem LLM (1, 2 e 5) são determinísticas. As medidas com LLM (3 e 4) usam o `OLLAMA_MODEL` configurado. O modelo efetivamente usado fica registrado no resultado: o padrão do ADR 0004 é o `gemma4:e4b`, e a reserva é o `qwen2.5:7b`.
