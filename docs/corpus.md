# Corpus e ingestão

## Fontes atuais

- `AguaHidratacaoESaude.md`
- `DepressaoAnsiedadeEstresseAlimentacao.md`
- `posicionamento_2022-alterado-nov-22-1.md`

## Observações

O corpus foi encontrado em Markdown transcrito a partir de PDFs, com menções a autores, instituições e referências bibliográficas. A base de conhecimento é relevante para nutrição e saúde, mas exige limpeza de paginação, listas e diagramas antes da ingestão.

## Política

- usar whitelist em `sources.yaml`
- reduzir conteúdo duplicado e quebrar apenas em estruturas sólidas
- preservar title, section, page, source_id e corpus_version
- `text_embed` deve seguir formato `[Documento > Seção] + texto`
- não permitir chunk sem `source_id` ou fora da whitelist
