# Sistema multiagentes (issue #99): resultados

Medição de 24/11/2026, pelos critérios de [`criterios.md`](criterios.md), escritos e commitados antes de rodar o LLM. Modelo `gemma4:e4b` no Ollama local (RTX 5060 de 8 GB), `think` desligado. Os arquivos `resultado_*.json` têm cada caso.

```bash
uv run python -m src.evaluation.multiagentes roteamento --split dev [--sem-llm]
uv run python -m src.evaluation.multiagentes busca|continuacao|compostas --split dev
```

## Resumo

| Medida | Critério | `dev` | `test` (uma vez) |
|---|---|---:|---:|
| Roteamento só com regras, casos claros | ≥ 0,85 | 1,000 (19) | **0,875** (8) |
| Roteamento com regras e LLM, todos os casos | ≥ 0,90 | 0,929 (28) | **0,917** (12) |
| Compostas: as duas áreas acionadas | ≥ 0,85 | 1,000 (10) depois do ajuste; 0,70 antes | **0,800** (5): **não cumpriu** |
| Continuação: termo do histórico e área certos | ≥ 0,80 | 0,833 (6) | **1,000** (4) |
| Trecho hipotético na busca: MRR de Nutrição | não piorar | 0,731 → 0,662 (**−0,069**) | 1,000 → 1,000 |
| Trecho hipotético na busca: MRR de Saúde Física | não piorar | 0,567 → 0,728 (+0,161) | 0,448 → 0,448 |

## Decisões tomadas com o `dev`

1. **Roteamento:** na primeira medição com o LLM, o acerto foi 0,75: quando a mensagem tinha termo das duas áreas, eu deixava o LLM decidir, e ele reduzia a uma área só (R03, R06, R17, R20, R22). **As regras passaram a decidir sempre que alguma área tem termo**, e o LLM só quando nenhuma tem: 0,929.
2. **Compostas:** só 0,70 acionavam as duas áreas, porque as regras olhavam a pergunta já reescrita pelo LLM, que às vezes tirava o termo de uma área (C01, C06), e "corre" faltava no vocabulário (C09). As regras passaram a olhar a mensagem original junto com a reescrita: 1,000 na conferência do roteamento das 10 compostas do `dev` (sem rodar os agentes de novo).
3. **Trecho hipotético (HyDE) na busca:** pela regra registrada, piorou o MRR de Nutrição no `dev` e fica **desligado por padrão** (`CULTIVA_HYDE_NA_BUSCA=false`). A chamada ao LLM continua ligada para a pergunta de continuação e para as mensagens sem termo de área (`CULTIVA_REESCRITA_LLM=true`). O ganho em Saúde Física no `dev` não se repetiu no `test`.
4. **Vocabulário:** "bike", "pedal" e "corre" entraram, a partir de erros do `dev`.

## Erros que ficaram

- **Compostas (`test`):** C13, "Dor nas costas pode ter relação com sobrepeso e alimentação?", foi só para Nutrição: "costas" não está no vocabulário de Saúde Física (só "lombar"), e as regras decidiram sem o LLM. O critério de 0,85 **não foi cumprido** no `test` (4 de 5). O vocabulário não foi ajustado a partir do `test`; a correção fica para um novo ciclo com casos novos.

- **Roteamento (`test`):** R37, "Hidratação durante o treino longo: água ou isotônico?", foi só para Saúde Física; "hidratação" e "isotônico" não estão no vocabulário de Nutrição. Só regras, os casos ambíguos e fora das áreas caem no Agente de Nutrição (comportamento de antes, que dá o "não sei" pelo cosseno); com o LLM, são decididos.
- **Roteamento (`dev`, com LLM):** R18 (sono e energia) foi às duas áreas, e R27 (tempo de tela) foi a Nutrição.
- **Continuação (`dev`):** T01 reescreveu "e para quem também é diabético?" como pergunta sobre diabéticos e perdeu a hipertensão.

## Perguntas compostas e Sincronizador

Com os agentes reais, o Sincronizador integrou **1 das 7** respostas de duas áreas no `dev` (antes do ajuste de roteamento) e **0 das 4** no `test`; nas outras, as respostas ficaram lado a lado, que é o comportamento seguro quando alguma frase da integração não tem citação literal. **A mediana foi de 183 s (`dev`) e 180 s (`test`) por pergunta composta**, com reescrita, dois agentes com síntese e citação por frase e o Sincronizador, todos no mesmo modelo local.

## Limitações

- Os casos têm o mesmo autor do código, e são poucos (40 de roteamento, 15 compostas, 10 de continuação, 23 de busca em Saúde Física).
- O golden de Saúde Física mede a fonte, não o Trecho: diz se a busca acha a diretriz certa, não o parágrafo.
- A latência do Chat geral com duas áreas (cerca de 3 minutos na RTX 5060) inviabilizava o uso interativo; a issue #107 a reduziu (seção abaixo).
- A taxa de integração do Sincronizador era baixa; a issue #107 a subiu, e o lado a lado continua quando a integração não passa na checagem.

## Latência e Sincronizador (issue #107)

Critérios registrados antes da medição em `latencia_criterios.md`; medida `latencia` de `src/evaluation/multiagentes.py`. Todas as medições foram feitas numa AMD RX 9060 XT (16 GB, ROCm), Ollama 0.40.18, `gemma4:e4b`, em 25 e 26/11/2026. Elas não são comparáveis com os 3 minutos da RTX 5060 acima. Os casos do `dev` são as 10 compostas e as 17 perguntas de uma área de `roteamento.json`, e o tipo é o que o Chat geral fez.

### Diagnóstico (`resultado_latencia_antes_dev.json`)

- **O modelo era recarregado em toda mensagem.**
  - A camada LLM do risco não passava o `num_ctx` e usava o padrão do Ollama (4096 nesta máquina). A reescrita, a síntese e o Sincronizador pedem 8192, e o Ollama recarrega o modelo quando o contexto muda.
  - A recarga estourava os 3 s da camada de risco, que **falhava em todas as mensagens**: só o léxico valia no produto. A chamada seguinte, a reescrita, pagava outra carga de cerca de 8 s.
  - O lote 4 da #48 mediu o classificador sozinho, sem chamadas intercaladas, e por isso não mostrou o problema.
- **A síntese não chega ao limite de tokens.** Nenhuma chamada dos agentes terminou por `num_predict`, e a geração de saída leva cerca de 4,6 s por agente. Por isso, encurtar a saída (regra 3) não foi tentado.
- **Por que o Sincronizador ficava lado a lado.** O motivo foi sempre frase sem citação literal. A citação era copiada do texto do agente, que é uma paráfrase, e não do Trecho; ou a frase vinha do grafo causal, que o Sincronizador não recebe. Uma frase assim derrubava a integração inteira.

### Mudanças e decisões (`dev`)

| Configuração | Uma área: mediana / p95 | Duas áreas: mediana / p95 | Integrada | Respostas com `llm_citacoes_validas` |
|---|---|---|---|---|
| Antes | 27,8 / 32,1 s | 46,1 / 50,9 s | 4/10 | 33 |
| 1. `num_ctx` igual em todas as chamadas | 16,0 / 21,0 s | 35,0 / 43,7 s | 3/10 | 32 |
| 4. Sincronizador (frase sem citação sai; resto integra) | 15,8 / 20,3 s | 35,3 / 43,3 s | 6/10 | 32 |
| 2. Agentes em paralelo (`OLLAMA_NUM_PARALLEL=2`) | 16,6 / 19,7 s | 28,9 / 33,9 s | 8/10 | 33 |

1. **`num_ctx` igual** (regra 1, adotada): nenhuma recarga fora do aquecimento, contra uma por pergunta antes. A camada de risco respondeu nas 27 perguntas, em cerca de 2,3 s. No lote 4 cego, o classificador manteve recall de 1,000 e precisão de 0,900 (`eval/risco/lote4_num_ctx_issue107.json`). O multimodal também passou a enviar o mesmo `num_ctx`.
2. **Sincronizador** (regra 4, adotada): a frase sem citação literal sai e o resto integra, como nos agentes. A integração exige pelo menos metade das frases e Trechos das duas áreas; o motivo novo de lado a lado é `uma_area_so`. Também mudaram o prompt, que diz que a citação vem dos trechos e não das respostas, e o limite de saída, que subiu para 2048 tokens (um JSON foi cortado em 1024). A integração passou de 3/10 para 6/10, com a mediana do Sincronizador igual (6,9 s). A checagem de citação não mudou.
3. **Agentes em paralelo** (regra 2, adotada e ligada por padrão): o p95 de duas áreas caiu 22% (43,3 para 33,9 s), sem perda de respostas com citações válidas. O ganho exige `OLLAMA_NUM_PARALLEL=2` no servidor do Ollama; sem isso, as duas requisições entram na fila e o tempo fica como em sequência.

### `test` (`resultado_latencia_final_test.json`, uma vez, configuração final)

| Tipo | n | Mediana | p95 |
|---|---|---|---|
| Uma área | 9 | 16,6 s | 17,2 s |
| Duas áreas | 4 | 25,8 s | 31,8 s |

- O Sincronizador integrou 2 de 4 perguntas; nas outras 2 (`uma_area_so`), o texto integrado citava Trechos de uma área só.
- A C13 foi só para Nutrição, como na #99 (vocabulário de "costas").

### Limitações

- **Poucos casos:** o p95 de cada grupo depende de 1 ou 2 perguntas.
- **Variação entre execuções:** com temperatura 0,1, a taxa de integração varia de uma execução para outra (4/10 e 3/10 sem mudança no Sincronizador).
- **Fidelidade das frases integradas:** a checagem garante a citação literal, mas a fidelidade dessas frases não foi julgada à parte.
- **Máquina:** a medição é de uma só máquina, de 16 GB. Numa GPU de 8 GB, as duas requisições paralelas disputam memória, e o ganho precisa ser medido lá.
