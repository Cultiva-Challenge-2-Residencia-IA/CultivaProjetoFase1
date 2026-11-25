# Latência do Chat geral e integração do Sincronizador (issue #107): critérios definidos antes da medição

Registrado em 25/11/2026, antes de rodar qualquer caso. Os casos são os de `compostas.json` e `roteamento.json` (issue #99), escritos antes desta issue.

## Medida

`uv run python -m src.evaluation.multiagentes latencia --split dev --rotulo <nome> [--paralelo]`

- **Casos:** no `dev`, as 10 perguntas compostas e as 17 de uma área só de `roteamento.json`. O tipo de cada pergunta (uma área ou duas) é o que o Chat geral fez, e não o esperado.
- **Aquecimento:** uma pergunta de cada área antes de medir. Ela carrega o índice e o modelo e não entra no resultado.
- **Por pergunta:**
  - o tempo de cada etapa (`RespostaDoChat.tempos`: portões, roteamento, cada Agente de área, Sincronizador e total);
  - cada chamada ao Ollama, com os tokens de entrada e de saída, o tempo de carga do modelo e o fim por limite de tokens;
  - o status da fundamentação de cada agente;
  - o modo e o motivo do Sincronizador.
- **Relato:** mediana e p95 do total para uma área e para duas áreas, mediana por etapa, taxa de integração do Sincronizador e motivos do lado a lado.
- **Máquina:** o "antes" e o "depois" rodam na mesma máquina e no mesmo dia, sem outro uso pesado da GPU. Toda tabela informa a GPU. A medição da #99 foi numa RTX 5060 e não é comparável com outra máquina.

## Regras de decisão (no `dev`)

Cada mudança é medida contra a configuração anterior e entra só se cumprir a sua regra.

1. **Opções iguais em todas as chamadas ao Ollama** (por exemplo, o mesmo `num_ctx`). Se a medição mostrar o modelo recarregado no meio de uma pergunta, a correção entra quando zera as recargas fora do aquecimento. A camada LLM do risco é conferida no lote 4 cego (`uv run python -m src.evaluation.risco_llm --lote 4`): recall e precisão não podem cair.
2. **Agentes de área em paralelo** (`CULTIVA_AGENTES_EM_PARALELO`), com o Ollama atendendo duas requisições (`OLLAMA_NUM_PARALLEL=2`). Fica ligado por padrão se cumprir as duas condições:
   - o p95 de duas áreas cai pelo menos 15%;
   - a contagem de respostas dos agentes com `llm_citacoes_validas` não cai mais de 2 casos.

   Se não cumprir, fica como opção desligada e o resultado é registrado.
3. **Menos saída na síntese** (`num_predict` ou campos do JSON). Só é tentada se a medição mostrar que a geração de tokens de saída domina o tempo dos agentes, ou que há fim por limite de tokens. Entra se cumprir as três condições:
   - o p95 do total cai pelo menos 15%;
   - a contagem de `llm_citacoes_validas` não cai mais de 2 casos;
   - uma amostra de 60 frases, julgada como a do RNF27 (`eval/fundamentacao/prompt_juiz.md`), tem pelo menos 80% de frases sustentadas (hoje 83%).
4. **Sincronizador** (prompt, limite de tokens ou tempo limite, conforme o motivo do lado a lado). Entra se, nas perguntas de duas áreas do `dev`:
   - integrar pelo menos 3 casos a mais que a configuração anterior;
   - manter a mediana do tempo do Sincronizador até 20% acima da anterior.

   A checagem de citação continua obrigatória: a integração só sai quando cada frase tem citação literal e a checagem aprova. Não há afrouxamento da checagem.

## `test`

Roda uma vez, com a configuração final e depois das decisões, só para relatar: p95 por tipo e taxa de integração. Nenhuma decisão usa o `test`.

## Limitações conhecidas

- Os casos são poucos (10 compostas e 17 de uma área no `dev`), então o p95 de cada grupo depende de 1 ou 2 perguntas.
- A temperatura de 0,1 deixa as respostas um pouco diferentes entre execuções, inclusive o caminho (LLM ou síntese extrativa).
