# Changelog — Golden Set de Saúde Física

## [1.0.0] - 2026-11-26

- Criação inicial do golden set de Saúde Física em `eval/golden/saude_fisica/{dev,test}.json` com 72 casos (36 `dev`, 36 `test`), todos em `status_revisao: rascunho` aguardando revisão humana.
- Definição de `caso.schema.json` estendendo a estrutura do golden v2 para Saúde Física (campos ricos, localizador `pagina_pdf`/`secao` e tipo `entre_abas`).
- Adição da CLI `src/evaluation/golden_saude_fisica` (`validar` e `estatisticas`) com bloqueio de vazamento `dev`/`test` e flag `--incluir-test` para o holdout.
- Geração de `MANIFEST.json` com hashes dos arquivos e dos Markdowns utilizados (normalizados em LF).
