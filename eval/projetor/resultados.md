# Projetor de contexto e Fatos do Usuário (issue #112): resultados

Critérios em [`criterios.md`](criterios.md), escritos e commitados antes de rodar o LLM. Modelo `gemma4:e4b` no Ollama local (RTX 5060 em 25/11/2026). Casos sintéticos escritos pelo autor do código: limitação registrada.

| Medida | Critério | `dev` | `test` |
|---|---|---:|---:|
| Extração: precisão | ≥ 0,90 | 1,000 (12 casos) | não medido |
| Extração: recall | ≥ 0,80 | 1,000 | não medido |
| Extração: falso fato | ≤ 1 por split | 0 | não medido |
| Seleção: recall | ≥ 0,80 | 0,833 (10 casos) | não medido |
| Seleção: vazamento | ≤ 0,10 | 0,000 | não medido |
| Resposta: uso do `[CONTEXTO]` | ≥ 0,70 | inconclusivo (ver abaixo) | não medido |

- **Seleção (`dev`):** a diabetes não foi entregue numa pergunta sobre exercício (S07), e o Chat geral não entregou o objetivo de treino (S06). Nenhum fato não relacionado foi entregue.
- **Resposta (`dev`):** a primeira rodada foi interrompida pela troca para os embeddings na GPU, e a segunda foi descartada, porque o esclarecimento da issue #104 ainda pedia dados pessoais e entrou antes do agente em 2 dos 4 casos. No único caso com fato entregue (S04), o gemma não escreveu nenhuma frase com `[CONTEXTO]`. Por isso o uso dos fatos passou para o redator (decisão de 25/11), que está desligado por padrão até a medição da issue #104.

## Pendente

O `test` de extração e seleção e a medição da resposta (`dev` e `test`) seguem na issue "Qualidade das respostas do chat: régua de perguntas reais e correção das causas" (#118), junto com a medição do chat inteiro contra perguntas reais. Sem a RTX 5060, cada resposta leva cerca de 1 minuto na GTX 1650.
