# Revisão de aprovação do corpus de Nutrição

**Data da revisão:** 2026-11-08  
**Escopo:** as 20 fontes com `approval_status: pendente` em `corpus/manifest.yaml`. Martins et al. (2013) e Souza e Backes (2020) já estavam aprovadas (PR #25, [`revisao-issue-8.md`](revisao-issue-8.md)) e não foram revistas aqui.  
**Resultado:** 19 fontes passam para `aprovado`, das quais duas com ressalva (Guia da SVB e Código de Ética do CFN). A SBAN (Água, Hidratação e Saúde) segue `pendente`. Com isso, 21 das 22 fontes estão aprovadas e 1818 dos 1873 Trechos entram no índice padrão.  
**Critério:** o critério mínimo da seção "Aprovação das fontes" do [`corpus/README.md`](../../README.md): checklist curta (origem verificável, documento vigente, sem conflito de interesse evidente e escopo adequado) e conferência de uma amostra de páginas contra o PDF, incluindo as de tabela.

> **Limite desta revisão.** A conferência foi feita com assistência de IA (Claude Code), por amostra e por comparação automática, e não página a página. `aprovado` significa que a fonte foi conferida e pode alimentar o RAG; não é aprovação jurídica nem científica ampla, e a licença não entra no gate (vale o aceite de risco do README). A revisão humana deste relatório no PR é parte da aprovação.

## Método

1. **Integridade.** `corpus/scripts/verify_corpus.py` passou nas 22 fontes: SHA-256 do PDF, do Markdown, do script e das configurações, marcadores `PDF_PAGE` e links `#page=N` em ordem, sem imagens exportadas.
2. **Tabelas, por números.** Em todas as páginas com tabela detectada nas 19 fontes, os números decimais do texto nativo do PDF (PyMuPDF) foram comparados com os do Markdown da mesma página. Resultado: nenhum número ausente, exceto na página 5 de Santos et al. (2019), uma tabela girada que saiu embaralhada. Essa página e a 6 já estavam fora dos Trechos (`skip_pages: [5, 6]` em `scripts/config/rag.yaml`, com `data_quality_note` no manifesto).

   | Fonte | Números em tabelas | Ausentes no Markdown |
   |---|---:|---:|
   | Guia Alimentar (2014) | 1 | 0 |
   | Fascículo 1 (2021) | 2 | 0 |
   | Guia da SVB (2012) | 858 | 0 |
   | Moreira e Rodrigues (2014) | 73 | 0 |
   | Salvi et al. (2020) | 146 | 0 |
   | Brisotto et al. (2022) | 31 | 0 |
   | ABESO (2022) | 53 | 0 |
   | SBME (2009) | 15 | 0 |
   | França et al. (2012) | 53 | 0 |
   | Santos et al. (2019) | 411 | 9 (página 5, já excluída) |
   | Jaime et al. (2009) | 419 | 0 |
   | Monteiro et al. (2010) | 474 | 0 |
   | Louzada et al., perfil nutricional (2015) | 347 | 0 |
   | Louzada et al., micronutrientes (2015) | 375 | 0 |
   | Rossetti (2015) | 30 | 0 |
   | Crispim et al. (2007) | 17 | 0 |
   | Fusco et al. (2020) | 41 | 0 |

   Azevedo et al. (2013) e o Código do CFN não têm tabelas detectadas.

3. **Páginas com alerta, visualmente.** As páginas com cobertura lexical abaixo de 90% e texto nativo relevante foram renderizadas e comparadas com o Markdown:

   | Fonte | Página | Cobertura | Resultado |
   |---|---:|---:|---|
   | Louzada et al., micronutrientes | 5 | 26,1% | Tabela 3 confere valor a valor. O cabeçalho "Quintos de consumo de alimentos ultraprocessados" saiu partido entre colunas; os dados estão corretos. |
   | Louzada et al., perfil nutricional | 5 | 94,2% | Tabela 1 confere linha a linha. |
   | Crispim et al. | 4 | 34,4% | Todo o texto corrido presente (frases conferidas, como as citações de Kalra e cols.). Falso alerta: a camada nativa repete o texto. |
   | ABESO | 223 | 82,5% | Texto fiel, incluindo percentuais de deficiências pós-cirurgia. Falso alerta por sobrescritos colados a números. |
   | Jaime et al. | 4 | 85,6% | Tabela 1 confere célula a célula. |

   Nos casos conferidos, o alerta de cobertura veio de tokenização (números partidos, sobrescritos, títulos duplicados na camada nativa), como o README já previa. As demais páginas com alerta da ABESO (69, 94, 125) e a página 6 da Louzada micronutrientes foram cobertas só pela comparação de números do item 2.

## Checklist por fonte

| Fonte | Origem verificável | Vigência | Conflito de interesse | Escopo | Decisão |
|---|---|---|---|---|---|
| Guia Alimentar para a População Brasileira (2014) | gov.br (Ministério da Saúde) | vigente | não | educativo | aprovado |
| Fascículo 1, Protocolos do Guia (2021) | BVS/MS | vigente | não | educativo | aprovado |
| Guia de dietas vegetarianas, SVB (2012) | **parcial**: URLs oficiais com 404; autoria e editora conferem com capa e créditos | edição de 2012 | não evidente | para profissionais, com prescrição | **aprovado com ressalva** |
| Moreira e Rodrigues (2014) | SciELO, DOI | artigo | não | estudo transversal | aprovado |
| Azevedo et al. (2013) | SciELO, DOI | artigo | não | revisão, em inglês | aprovado |
| Salvi et al. (2020) | SciELO, DOI | artigo | não | estudo transversal | aprovado |
| **SBAN, Água, Hidratação e Saúde (2016)** | **não**: origem pública não identificada | não confirmada | **sim, evidente**: rótulos "Nestle_Folheto_Aguas_MaterialCientifico" | educativo | **pendente** |
| Brisotto et al. (2022) | portal da RBTC | artigo | não | estudo transversal | aprovado |
| ABESO, Posicionamento (2022) | PDF recebido da equipe; obra identificada por ISBN 978-85-93044-01-4 e ficha catalográfica | vigente | não evidente | para profissionais, com prescrição (RN01) | aprovado |
| SBME, Diretriz (2009) | SciELO | diretriz de 2009, sem substituta localizada | não | para profissionais | aprovado |
| França et al. (2012) | SciELO | artigo | não | estudo | aprovado |
| Santos et al. (2019) | SciELO | artigo | não | estudo transversal | aprovado (páginas 5 e 6 fora dos Trechos) |
| Jaime et al. (2009) | SciELO | artigo | não | estudo | aprovado |
| Monteiro et al. (2010) | SciELO | artigo | não | revisão (NOVA) | aprovado |
| Louzada et al., perfil nutricional (2015) | SciELO | artigo | não | estudo | aprovado |
| Louzada et al., micronutrientes (2015) | SciELO | artigo | não | estudo | aprovado |
| Rossetti (2015) | portal da revista (Unicamp) | artigo | não | revisão | aprovado |
| Código de Ética do CFN (Res. 599/2018) | cfn.org.br | **não confirmada**: a Res. 856/2026 pode tê-la revogado | não | norma profissional | **aprovado com ressalva** |
| Crispim et al. (2007) | SciELO | artigo | não | revisão | aprovado |
| Fusco et al. (2020) | SciELO | artigo | não | estudo | aprovado |

## Decisões

- **SBAN segue `pendente`.** O critério exige ausência de conflito de interesse evidente, e os rótulos de página indicam material produzido para a Nestlé (RN16). Pode ser reavaliada se a SBAN confirmar autoria e patrocínio.
- **CFN aprovado com ressalva.** A vigência da Resolução 599/2018 não foi confirmada; a ressalva está em `data_quality_note`. Reavaliar quando o texto oficial da Resolução 856/2026 for localizado.
- **SVB aprovado com ressalva.** A equivalência do PDF recebido com a versão publicada não foi confirmada; a ressalva está em `data_quality_note`. O conteúdo de prescrição só pode ser usado para fins educativos (RN01).
- As fontes dirigidas a profissionais (SVB, ABESO, SBME, CFN) entram no índice para contextualizar limites e explicar evidências. Nenhuma autoriza o produto a prescrever ou diagnosticar (RN01 a RN03).

## Achado não bloqueante

Trechos de itálico colados no Markdown, como `Alimentos_in natura_ou`, viram `Alimentosin naturaou` nos Trechos, porque `clean_inline` em `corpus/scripts/prepare_rag.py` remove os marcadores `_` sem inserir espaço. Foram encontradas 10 ocorrências, todas nas duas fontes de Louzada et al. Isso prejudica a busca lexical por "in natura" nesses Trechos. A correção deve ir numa issue própria, porque altera os Trechos de outras fontes; não foi feita neste PR.

## Arquivos alterados

- `corpus/manifest.yaml`: `approval_status: aprovado` em 19 fontes e `data_quality_note` no Guia da SVB e no Código do CFN.
- `corpus/nutricao/rag/*.jsonl`: regenerados por `prepare_rag.py`; muda apenas o campo `approval_status` dos Trechos (conferido registro a registro).
