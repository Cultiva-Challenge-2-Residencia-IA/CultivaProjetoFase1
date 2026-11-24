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
- A latência do Chat geral com duas áreas (cerca de 3 minutos na RTX 5060) inviabiliza o uso interativo sem otimização: paralelizar os agentes, encurtar o JSON da síntese ou um modelo mais rápido.
- A taxa de integração do Sincronizador é baixa; o lado a lado mantém as citações, mas não cruza as áreas.
