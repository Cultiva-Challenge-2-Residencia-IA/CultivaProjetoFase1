# Sistema multiagentes (issue #99): critérios definidos antes da medição

Registrado em 24/11/2026, antes de rodar qualquer caso com o LLM. Os casos foram escritos pela mesma pessoa que escreveu o código (feliperodri0, com Claude), sem olhar resultados; isso é uma limitação, registrada em cada resultado.

Configuração medida: `gemma4:e4b` no Ollama local (ADR 0004), `think` desligado, temperatura 0,1.

## 1. Roteamento (`roteamento.json`)

- **Casos:** mensagens com as áreas esperadas: uma área, as duas, fora das áreas ou Estudos. `dev` para ajustar, `test` rodado uma vez.
- **Métrica:** acerto do conjunto de áreas por caso (Estudos e fora das áreas contam como conjunto vazio, com a mensagem certa).
- **Duas configurações:** só regras (o que o CI mede) e regras com o LLM de desempate (o produto com Ollama).
- **Critérios:**
  - só regras, nos casos `clara` (termos de uma ou das duas áreas): acerto ≥ 0,85. Vira teste do CI;
  - regras com LLM, em todos os casos: acerto ≥ 0,90.

## 2. Perguntas compostas (`compostas.json`)

- **Casos:** mensagens que envolvem as duas áreas.
- **Métricas:** fração em que as duas áreas são acionadas; fração em que o Sincronizador integra (`integrada`) em vez de deixar lado a lado; e, nas integradas, a checagem de citação aprovada (é ela que decide, por construção).
- **Critérios:** as duas áreas acionadas em ≥ 0,85 dos casos. A taxa de integração é só relatada: lado a lado é o comportamento seguro, não uma falha.

## 3. Reescrita de consulta na busca (golden v2 de Nutrição e golden de Saúde Física)

- **Comparação pareada, no mesmo índice:** busca só com a pergunta (o caminho de antes) contra a busca com a pergunta, a subpergunta e o trecho hipotético da reescrita, fundidos por RRF.
- **Nutrição:** casos `responder` do golden v2 `dev` com Trechos julgados; métricas por Trecho (MRR e recall@4) de `benchmark_v2.metricas_de_recuperacao`.
- **Saúde Física:** golden novo (`golden_saude_fisica.json`), com a fonte esperada; métricas por fonte (acerto@4 e MRR da primeira fonte esperada).
- **Regra de decisão:** a reescrita fica ligada por padrão (`CULTIVA_REESCRITA_LLM=true`) se, no `dev` de Nutrição **e** no `dev` de Saúde Física, a média de MRR com reescrita não for menor que a sem reescrita. Se piorar em qualquer um, fica desligada por padrão (só o Sincronizador usa o LLM). O `test` roda uma vez, depois da decisão, e só mede.

## 4. Pergunta de continuação (`continuacao.json`)

- **Casos:** pares (mensagem anterior, mensagem de continuação) com a área esperada e um termo que a pergunta completa precisa trazer do histórico.
- **Métrica:** fração em que a pergunta completa da reescrita traz o termo e a área sai certa.
- **Critério:** ≥ 0,80, com o LLM. Sem LLM, a continuação não é resolvida (limitação registrada).

## Fora destes critérios

A qualidade das respostas do Agente de Saúde Física (fidelidade às fontes) não é medida aqui; usa a mesma checagem de citação por frase do Agente de Nutrição, e a amostra humana segue pela #12.
