# Corpus e ingestão

## Fontes atuais

- `AguaHidratacaoESaude.md`
- `DepressaoAnsiedadeEstresseAlimentacao.md`
- `posicionamento_2022-alterado-nov-22-1.md`

## Observações

O corpus foi encontrado em Markdown transcrito a partir de PDFs, com menções a autores, instituições e referências bibliográficas. A base de conhecimento é relevante para nutrição e saúde, mas exige limpeza de paginação, listas e diagramas antes da ingestão.

## Contrato M1

No incremento T1-01, `corpus/manifest.yaml` é o manifesto ativo e a única whitelist consumida pelo carregador. A referência a `sources.yaml` na política abaixo permanece como proposta histórica; não é lida pelo código atual. O manifesto está vazio, portanto nenhum Markdown do corpus está autorizado para ingestão até que suas fontes sejam explicitamente aprovadas e declaradas.

## Política

- usar whitelist em `sources.yaml`
- reduzir conteúdo duplicado e quebrar apenas em estruturas sólidas
- preservar title, section, page, source_id e corpus_version
- `text_embed` deve seguir formato `[Documento > Seção] + texto`
- não permitir chunk sem `source_id` ou fora da whitelist
