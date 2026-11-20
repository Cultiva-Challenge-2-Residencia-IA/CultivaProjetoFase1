# Painel de observabilidade no Langfuse

Painel da issue #46 (critério de aceite: taxa de acionamento do risco, do guardrail e da síntese extrativa, e latência p95, RNF29). O Langfuse não tem API para criar painéis, então ele é montado à mão na interface. Este documento é a especificação: com ele, qualquer pessoa da equipe recria o painel igual.

Os dados vêm de `src/observabilidade.py` e de `consult()`:

- trace `consulta_nutricao`, com a observação raiz `consult` e um span por nó do grafo (`guardrail_entrada`, `retrieve`, `taco`, `grafo_causal`, `sintese`, `guardrail_saida`);
- geração `ollama`, com o modelo, os tokens e a latência da chamada ao LLM;
- scores de cada consulta (`scores_da_resposta`):
  - `tipo_resposta`, categórico;
  - indicadores 0/1, cuja média é a taxa: `sintese_extrativa`, `citacoes_validas`, `nao_sei`, `risco_acionado`, `prompt_injection`, `guardrail_lei_8234`;
- score `resposta_incorreta`, gravado pelo `POST /feedback/incorrect` (RF-IA15);
- `release` do trace: o commit do Git (ou `LANGFUSE_RELEASE`); `version`: a versão do prompt.

## Como montar

1. No projeto do Langfuse, abra **Dashboards** no menu lateral e clique em **New dashboard**. Nome: `CULTIVA: consultor de Nutrição`.
2. Para cada linha da tabela abaixo, clique em **Add widget** e depois em **Create new widget**. Preencha os campos e clique em **Save**. O widget entra no painel.
3. Em cada widget, adicione o filtro `Environment = desenvolvimento`, para separar os testes de uma futura produção.
4. Arraste os widgets para organizar o painel e ajuste o período no seletor do canto superior. Comece com os últimos 7 dias.

| # | Nome do widget | View | Métrica e agregação | Filtros | Quebra (breakdown) | Gráfico |
|---|---|---|---|---|---|---|
| 1 | Consultas por dia | Traces | Count | Trace name = `consulta_nutricao` | nenhuma | Line |
| 2 | Latência p95 da consulta (RNF29) | Observations | Latency, p95 | Name = `consult` | nenhuma | Line |
| 3 | Latência p95 agora | Observations | Latency, p95 | Name = `consult` | nenhuma | Number |
| 4 | Latência p95 do LLM por modelo | Observations | Latency, p95 | Name = `ollama` | Provided model name | Bar |
| 5 | Taxas por consulta | Scores (numeric) | Value, average | Name em `sintese_extrativa`, `citacoes_validas`, `nao_sei`, `risco_acionado`, `prompt_injection`, `guardrail_lei_8234` | Name | Line |
| 6 | Tipo de resposta | Scores (categorical) | Count | Name = `tipo_resposta` | String value | Pie |
| 7 | Respostas marcadas como incorretas (RF-IA15) | Scores (numeric) | Value, sum | Name = `resposta_incorreta` | nenhuma | Bar |
| 8 | Erros do LLM | Observations | Count | Name = `ollama`, Level = `ERROR` | nenhuma | Bar |
| 9 | Tokens por dia | Observations | Total tokens, sum | Type = `GENERATION` | Provided model name | Bar |
| 10 | Taxas por versão do código | Scores (numeric) | Value, average | os mesmos nomes do widget 5 | Release | Bar |

## Como ler

- **Widget 5:** a média de um indicador 0/1 é a taxa. Exemplo: `sintese_extrativa` em 0,10 quer dizer que 10% das consultas caíram na síntese extrativa, porque o LLM falhou, estourou o tempo ou teve a citação bloqueada.
- **`citacoes_validas`** só existe quando o LLM respondeu com citações. A média é a conformidade da citação por frase da #12.
- **Widgets 2 e 3:** o RNF29 pede p95 de até 3 s por chamada de LLM. A consulta inteira inclui a busca e o carregamento do modelo, então o p95 dela é maior.
- **Widget 8:** erro do LLM quase sempre é tempo esgotado. Se aparecer junto com `sintese_extrativa` alta, confira se outro modelo está ocupando a GPU (`curl localhost:11434/api/ps`).
- **Widget 10:** compara as taxas antes e depois de um merge. Uma queda de `citacoes_validas` numa versão nova indica regressão.

## Limites

- O painel só tem dados de quem roda com o Langfuse ligado (`CULTIVA_LANGFUSE=true` e as chaves). O CI e o benchmark não enviam nada.
- Pelo ADR 0003, o projeto na nuvem só recebe perguntas sintéticas, do golden set ou desidentificadas. Os números do painel refletem testes da equipe, não uso real.
- Os nomes dos campos acima são os da interface do Langfuse em novembro de 2026 e podem mudar.
