# Relatório do corpus nutrição

## 1) Resumo executivo

Foram identificados 3 artefatos de conteúdo em `corpus/nutricao`:

- `AguaHidratacaoESaude.md`
- `DepressaoAnsiedadeEstresseAlimentacao.md`
- `posicionamento_2022-alterado-nov-22-1.md`

Os três estão em português brasileiro, com forte presença de transcrição de PDFs, citações, listas e tabelas. O conjunto é relevante para a frente de nutrição, mas exige normalização antes da ingestão porque alguns trechos trazem paginação, texto duplicado, imagens e formatação de PDF.

## 2) Formato e idioma

- Formato predominante: Markdown legível por humano, em texto estruturado, com tabelas em Markdown e alguns blocos de conteúdo vindos de PDF transcritos.
- Idioma: português do Brasil, com trechos em inglês em citações, títulos e referências bibliográficas.
- Editor e fonte aparentes: texto transcrito a partir de PDFs acadêmicos e posicionamento institucional; há menções a autores, instituições e referências bibliográficas, sem metadados estruturados completos;
- A fonte final dos PDFs parece estar em documentação educacional e institucional, não em artigos originais carregados no repo.

## 3) Tamanho e estrutura

| Arquivo | Estimativa de tokens | Estrutura principal |
| --- | ---: | --- |
| `AguaHidratacaoESaude.md` | ~8.4k | Introdução, capítulos, tabelas, referências |
| `DepressaoAnsiedadeEstresseAlimentacao.md` | ~8.0k | Introdução, método, resultados, discussão, referências |
| `posicionamento_2022-alterado-nov-22-1.md` | ~113.1k | Capítulos longos, listas, tabelas, referências detalhadas |

Observações:

- O terceiro arquivo tem volume muito maior e exige chunking por estrutura para não cair em excesso de token por chunk.
- Há muito conteúdo repetitivo em cabeçalhos, páginas e listas de conteúdo.
- Há elementos visuais como `[Imagem: ...]` e blocos de diagramas que devem ser preservados como metadados, mas não processados como conteúdo científico central.

## 4) Riscos de parsing

- Quebras artificiais de linha e paginação do PDF;
- Títulos repetidos e rodapés duplicados;
- Tabelas com HTML/Markdown quebrado, especialmente em documentos transcritos;
- Blocos com formatação ambígua, como `**H > 51**` ou `**1.**` em tabelas;
- Referências em inglês e caracteres de citações, marcas de texto e listas aninhadas;
- Diagramas visuais sem texto selecionável, difíceis de indexar sem etapa de limpeza manual;
- Várias referências indiretas e menções de autores sem bastidores claros.

## 5) Riscos de uso no agente

- Não pode haver inferência de dados que não estejam no corpus;
- A fonte mínima de verdade é o corpus e os PDFs originais, não a memória do agente;
- O parser precisa ignorar elementos visuais e manter metadados de título, seção e página;
- O chunking precisa preservar listagem e tabelas sem fragmentar conteúdo científico essencial.

## 6) Conclusão

O corpus tem qualidade suficiente para uma POC de RAG nutrícia, mas exige padronização e ingestão controlada. O principal dado faltante é a whitelist de fontes e o manifesto de origem; sem isso, não é possível encaixar RN16 e a reingestão idempotente.
