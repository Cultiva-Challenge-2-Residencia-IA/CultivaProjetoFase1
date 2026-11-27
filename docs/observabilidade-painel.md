# Painel de observabilidade no Langfuse

Painel da issue #46 (critério de aceite: taxa de acionamento do risco, do guardrail e da síntese extrativa, e latência p95, RNF29). O Langfuse não tem API para criar painéis, mas importa painéis e widgets em JSON. Os arquivos ficam em [`observabilidade-painel/`](observabilidade-painel/):

- `painel-cultiva.json`: o painel inteiro, com os 11 cards posicionados;
- `widgets/*.json`: um arquivo por card, para importar um de cada vez.

Os dados vêm de `src/observabilidade.py` e de `consult()`:

- trace `consulta_nutricao`, com a observação raiz `consult` e um span por nó do grafo (`guardrail_entrada`, `retrieve`, `taco`, `grafo_causal`, `sintese`, `guardrail_saida`);
- geração `ollama`, com o modelo, os tokens e a latência da chamada ao LLM;
- scores de cada consulta (`scores_da_resposta`):
  - `tipo_resposta`, categórico;
  - indicadores 0/1, cuja média é a taxa: `sintese_extrativa`, `citacoes_validas`, `nao_sei`, `risco_acionado`, `prompt_injection`, `guardrail_lei_8234`;
- score `resposta_incorreta`, gravado pelo `POST /feedback/incorrect` (RF-IA15);
- `release` do trace: o commit do Git (ou `LANGFUSE_RELEASE`); `version`: a versão do prompt.

## Como importar

**O painel inteiro:** no projeto do Langfuse, abra **Dashboards**, crie um painel vazio (**New dashboard**) e arraste o arquivo `painel-cultiva.json` para cima da página dele. O Langfuse não tem botão para importar painel; a importação é só por arrastar e soltar. Soltar o arquivo num painel que já tem os cards duplica os cards.

**Um card:** no painel, **Add widget**, **Create new widget**, **Import**, e escolha o arquivo em `widgets/`. Confira o formulário e clique em **Save**.

O Langfuse descarta, na importação, valores de filtro que ainda não existem no projeto (por exemplo, `resposta_incorreta` antes do primeiro feedback). Se um filtro sumir, adicione-o à mão.

## Os cards

Todos usam o período escolhido no seletor do topo do painel (padrão: últimos 7 dias). O período vale para o painel inteiro, não para cada card.

| Arquivo | Título | O que mostra |
|---|---|---|
| `06-taxas-no-periodo.json` | Taxas no período (% das consultas) | Fração das consultas em cada situação: síntese extrativa, citações válidas, "não sei", risco, prompt injection e guardrail da Lei 8.234 |
| `03-latencia-p95-agora.json` | Tempo de resposta no período (p95, RNF29) | Tempo em que 95% das consultas terminaram, num único número |
| `07-tipo-de-resposta.json` | Como cada consulta foi respondida | Quantas consultas seguiram cada caminho (`tipo_resposta`); o risco aparece como `risco` (léxico) ou `risco_llm` (camada LLM da #48), e a lacuna do filtro de relevância (#105; o filtro está desligado por padrão) como `lacuna_de_relevancia`, que também conta em `nao_sei` |
| `05-taxas-por-dia.json` | Taxas por dia (% das consultas) | As mesmas taxas, dia a dia |
| `02-latencia-p95-consulta.json` | Tempo de resposta por dia (p95, RNF29) | O p95 da consulta, dia a dia |
| `01-consultas-por-dia.json` | Consultas por dia | Quantidade de traces `consulta_nutricao` |
| `04-latencia-llm-por-modelo.json` | Tempo do LLM por modelo (p95) | p95 das chamadas ao Ollama, por modelo |
| `09-erros-do-llm.json` | Falhas do LLM por dia | Chamadas ao Ollama com nível `ERROR` |
| `08-respostas-incorretas.json` | Respostas marcadas como incorretas (RF-IA15) | Soma do score `resposta_incorreta` |
| `10-tokens-por-dia.json` | Tokens do LLM por dia | Soma dos tokens das gerações |
| `11-taxas-por-versao.json` | Taxas por versão do código | Cada taxa por `release` (commit), para comparar antes e depois de um merge |

## Como ler

- **Taxas:** cada indicador vale 0 ou 1 por consulta, então a média é a taxa. Exemplo: `sintese_extrativa` em 0,10 quer dizer que 10% das consultas caíram na síntese extrativa, porque o LLM falhou, estourou o tempo ou teve a citação bloqueada.
- **`citacoes_validas`** só existe quando o LLM respondeu com citações. A média é a fração das respostas do LLM aprovadas pela checagem da citação por frase (#12).
- **Tempo de resposta:** o RNF29 pede p95 de até 3 s por chamada de LLM. A consulta inteira inclui a busca e o carregamento do modelo, então o p95 dela é maior.
- **Falhas do LLM:** quase sempre é tempo esgotado. Se aparecerem junto com `sintese_extrativa` alta, confira se outro modelo está ocupando a GPU (`curl localhost:11434/api/ps`).

## Limites

- **Nomes repetidos com os experimentos.** O `langfuse_experimento.py` grava métricas de avaliação com os mesmos nomes `citacoes_validas` e `sintese_extrativa`, com outra definição (por exemplo, `citacoes_validas` vale 0 por definição na configuração "LLM puro"). Essas notas entram na média dos cards de taxas. Para ler só o produto, escolha no seletor do topo um período sem experimentos; os experimentos se comparam na tela **Experiments** do Langfuse.
- O painel só tem dados de quem roda com o Langfuse ligado (`CULTIVA_LANGFUSE=true` e as chaves). O CI e o benchmark não enviam nada.
- Pelo ADR 0003, o projeto na nuvem só recebe perguntas sintéticas, do golden set ou desidentificadas. Os números do painel refletem testes da equipe, não uso real.
- O formato dos JSON é o do Langfuse em novembro de 2026 (`$langfuseDashboard` e `$langfuseWidget`, versão 1) e pode mudar.
