# Changelog — Golden Set de Saúde Física

## [1.1.0] - 2026-11-26

- Revisão humana manual concluída e aprovada em todos os 72 casos (`dev.json` e `test.json`): `status_revisao: "revisado"`, `autoria.revisao: "revisado"`, `autoria.revisor: "IngridHNobrega"`.
- Refinamento de `dev.json` (mantendo `test.json` congelado como holdout): perguntas ajustadas para linguagem natural de jovens adultos/estudantes (18+), remoção de extrapolações não sustentadas nas `resposta_referencia`, casos `fora_de_escopo` mais realistas e `pontos_proibidos` com padrões `regex:` verificáveis.
- Melhoria no avaliador (`src/evaluation/golden_saude_fisica/avaliador.py`) e CLI (`__main__.py`): suporte real a `recusar_adversarial`, `roteamento_ok` (`entre_abas`), `portao_risco_ok`, validação de `citacoes_validas` contra `evidencias` e suporte a `regex:` em `pontos_proibidos`.

## [1.0.0] - 2026-11-26

- Criação inicial do golden set de Saúde Física em `eval/golden/saude_fisica/{dev,test}.json` com 72 casos (36 `dev`, 36 `test`), todos em `status_revisao: rascunho` aguardando revisão humana.
- Definição de `caso.schema.json` estendendo a estrutura do golden v2 para Saúde Física (campos ricos, localizador `pagina_pdf`/`secao` e tipo `entre_abas`).
- Adição da CLI `src/evaluation/golden_saude_fisica` (`validar` e `estatisticas`) com bloqueio de vazamento `dev`/`test` e flag `--incluir-test` para o holdout.
- Geração de `MANIFEST.json` com hashes dos arquivos e dos Markdowns utilizados (normalizados em LF).
