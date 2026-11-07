# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Regras do projeto

As regras de trabalho estão em [AGENTS.md](AGENTS.md) e valem integralmente aqui. Leia-o junto com [docs/contexto-projeto.md](docs/contexto-projeto.md) e [corpus/README.md](corpus/README.md) antes de alterar o repositório. Em resumo:

- O CULTIVA é um app de apoio educativo/organizacional (18+) em Nutrição, Saúde Física e Estudos. A IA **não** diagnostica nem prescreve.
- Requisitos (RN, RF-A, RF-IA, RNF) e a arquitetura vêm do repositório [Documentacao-Cultiva](https://github.com/Cultiva-Challenge-2-Residencia-IA/Documentacao-Cultiva). A arquitetura é uma **proposta provisória, ainda não validada**. Classifique as afirmações em: requisito aprovado / documentado, aprovação não confirmada / proposta técnica / hipótese.
- Etapa atual: **corpus de Nutrição**. Ingestão, RAG, agentes e infraestrutura só com pedido explícito.
- Escreva em português do Brasil, como o restante do repositório.

## Estado real do código

- `src/` (api, agents, rag, broker, guardrails), `eval/`, `infra/`, `specs/`, `notebooks/`, `docs/adrs|ripd|rubric` contêm apenas `.gitkeep`. Eles espelham a arquitetura proposta e **não** representam funcionalidades implementadas.
- O único código executável é o pipeline de corpus em `corpus/scripts/` (Python 3.11, PyMuPDF). Não existe aplicação, linter nem suíte de testes. O "teste" disponível é `verify_corpus.py`.

## Comandos (na raiz do repositório)

```bash
python3 -m venv corpus/.venv
corpus/.venv/bin/python -m pip install -r corpus/scripts/requirements.txt

# Verificação de integridade/rastreabilidade de todas as fontes (não aprova conteúdo)
corpus/.venv/bin/python corpus/scripts/verify_corpus.py

# Regenerar Markdown + relatório de UMA fonte (id do manifest.yaml)
corpus/.venv/bin/python corpus/scripts/convert_pdfs.py --source <id> --overwrite

# Primeira execução / originais ou modelo OCR ausentes
corpus/.venv/bin/python corpus/scripts/convert_pdfs.py --download --download-ocr
```

Após cada alteração documental, rode `git diff --check`. `corpus/.venv/` e `corpus/.cache/` (modelo OCR `por.traineddata`, verificado por SHA-256) são ignorados pelo Git.

## Arquitetura do pipeline de corpus

O fluxo atravessa vários arquivos, encadeados por hashes:

1. **`corpus/manifest.yaml`**: catálogo único (`version: 1`, `sources`). Cada fonte declara `id`, `source`, `license`, `version`, `sha256`, `pdf_pages`, caminhos (`original_path`, `markdown_path`, `report_path`, `conversion_config`) e status (`conversion_status`, `approval_status`, `intended_use_license_review`). Não crie `sources.yaml`. Os scripts **leem** o manifesto, mas nunca o alteram.
2. **`corpus/nutricao/originais/*.pdf`**: bytes preservados. O hash precisa corresponder ao manifesto, e os originais nunca são sobrescritos.
3. **`corpus/scripts/config/<fonte>.yaml`**: decisões por fonte, vinculadas ao SHA-256 do PDF (`sparse_page_decisions`, `ocr_regions`, `page_overrides`, `replacements`, `page_notes`, `strip_false_strikethrough_pages`). Substituições estritas falham se o trecho esperado mudar.
4. **`corpus/scripts/ajustes/*.md`**: transcrições manuais de páginas problemáticas, referenciadas em `page_overrides`.
5. **`convert_pdfs.py`** gera `nutricao/markdown/<nome>.md`, com `<!-- PDF_PAGE: N -->`, âncora `pagina-pdf-NNN` e link `...pdf#page=N` em cada página física (base 1, sem imagens exportadas). Também gera `nutricao/relatorios/<nome>.json`, com diagnóstico por página, OCR bruto, cobertura lexical (limiar de 98%, apenas diagnóstico) e hashes do PDF, Markdown, script, config e ajustes.
6. **`verify_corpus.py`** recalcula os hashes e falha se: o PDF divergir; o **Markdown for editado após a conversão**; `convert_pdfs.py`, a configuração ou um ajuste mudar sem regeneração; marcadores/links de página faltarem ou estiverem fora de ordem; ou houver imagem `![]()`. Ele não confere o `approval_status`.

Consequências práticas:

- Correções de transcrição devem ir para `config/` ou `ajustes/` e ser seguidas de `--source <id> --overwrite`. Edições diretas no `.md` quebram a verificação e são perdidas na regeneração.
- Qualquer mudança em `convert_pdfs.py` invalida os relatórios de **todas** as fontes até que sejam regeneradas.
- Há um único status de aprovação por fonte, `approval_status` (`pendente` ou `aprovado`), que vive só no manifesto (decisão de 06/11/2026; veja `corpus/README.md`). `convert_pdfs.py` se recusa a converter fonte com `approval_status` diferente de `pendente`, para não regenerar uma fonte aprovada por engano, e o verificador não exige nenhum status.
- Para incluir uma nova fonte, siga a seção "Como incluir outro documento" em [corpus/README.md](corpus/README.md). Não copie a licença de outra fonte e use `pendente` quando ela for desconhecida.

## Inconsistência conhecida

[docs/contexto-projeto.md](docs/contexto-projeto.md) (03/11/2026) está desatualizado em relação ao corpus:

- afirma `sources: []` e que os diretórios ainda não existem;
- propõe `originais/<id>/<versao>/documento.<ext>`, mas o layout implementado é plano (`originais/<nome>.pdf`), com a versão registrada no manifesto e no nome do arquivo.

Use `corpus/README.md` e `manifest.yaml` como referência do estado atual. Não altere o contexto sem pedido.
