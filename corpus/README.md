# Corpus científico de Nutrição

Esta etapa obtém os PDFs oficiais e produz transcrições em Markdown, com marcadores e links a todas as páginas dos originais. **Os dois documentos permanecem com revisão e aprovação pendentes.** Conversão e conferência amostral não tornam uma fonte elegível para responder aos usuários.

O corpus científico é separado dos dados pessoais. Não colocar aqui perfis, registros de hábitos/saúde, conversas, fotos, áudios ou PDFs enviados por usuários.

## Fontes e procedência

O catálogo é [`manifest.yaml`](manifest.yaml), mantendo `version: 1` e `sources`. Os campos `id`, `source`, `license` e `version` foram preservados e complementados com título, instituições, ano/edição, endereço efetivo de download, caminhos, SHA-256 e status.

| Documento | Edição obtida | Páginas físicas do PDF | Origem utilizada |
|---|---|---:|---|
| Guia alimentar para a população brasileira | 2ª edição, 1ª reimpressão, Ministério da Saúde, 2014 | 158 | [BVS / Ministério da Saúde](https://bvsms.saude.gov.br/bvs/publicacoes/guia_alimentar_populacao_brasileira_2ed.pdf) |
| Fascículo 1 — bases teóricas e metodológicas e protocolo para a população adulta | 1ª edição, versão eletrônica, Ministério da Saúde e USP, 2021 | 28 | [BVS / Ministério da Saúde](https://bvsms.saude.gov.br/bvs/publicacoes/protocolos_guia_alimentar_fasciculo1.pdf) |

Consulta e obtenção: **03/11/2026**. O endereço do Guia informado no pedido redirecionou para autenticação; o arquivo foi obtido na BVS oficial. A edição foi identificada na capa e nos créditos, mas não foi possível comparar seus bytes com os do endereço indisponível. As fichas catalográficas indicam 156 e 26 páginas, respectivamente; o total físico inclui páginas adicionais. Os marcadores desta conversão usam sempre a posição física no PDF, começando em 1.

Ambos os PDFs declaram **CC-BY-NC-SA-4.0** na página física 3: atribuição, uso não comercial e compartilhamento pela mesma licença. Originais e textos derivados mantêm a atribuição aos autores institucionais e essa licença. As transformações realizadas são extração, estruturação em Markdown, OCR pontual e correções de transcrição identificadas; não há endosso do Ministério ou da USP ao CULTIVA. A compatibilidade dessa licença com o uso futuro pretendido pelo produto permanece **pendente**.

## Organização

```text
corpus/
  manifest.yaml
  nutricao/
    originais/       # PDFs obtidos, sem alteração dos bytes
    markdown/       # .md convertidos, ainda pendentes de revisão
    relatorios/     # JSON por documento: diagnóstico por página e hashes
  scripts/
    convert_pdfs.py
    verify_corpus.py
    requirements.txt
    config/         # decisões de OCR e correções vinculadas ao SHA-256
    ajustes/        # transcrições pontuais de páginas problemáticas
```

O diretório `markdown/` contém **candidatos à revisão**, conforme esta etapa autorizada. Não interpretar sua presença ali como revisão concluída. As orientações anteriores em `docs/contexto-projeto.md` registram a situação antes da obtenção dos documentos; seus arquivos locais foram preservados.

## Dependências e execução

Ambiente utilizado: Python **3.11**, PyMuPDF/PyMuPDF4LLM **2.1**, PyYAML **6.0.3**, Pillow **13.0.0** e dependências fixadas em `scripts/requirements.txt`. PyMuPDF inclui renderização, análise local de layout e suporte a OCR via MuPDF/Tesseract. Não são necessários Poppler, serviço de OCR remoto, chave de API ou LLM generativo. `curl` é usado apenas quando há download solicitado. Para OCR é necessário o modelo português `por.traineddata`, baixado do repositório oficial `tesseract-ocr/tessdata_fast` e validado por SHA-256.

Na raiz do repositório:

```bash
python3 -m venv corpus/.venv
corpus/.venv/bin/python -m pip install -r corpus/scripts/requirements.txt

# Primeira execução: baixa apenas PDFs/modelo OCR ausentes.
corpus/.venv/bin/python corpus/scripts/convert_pdfs.py --download --download-ocr

# Os derivados já estão entregues neste checkout. Para regenerá-los:
corpus/.venv/bin/python corpus/scripts/convert_pdfs.py --download-ocr --overwrite

# Verificação dos artefatos locais:
corpus/.venv/bin/python corpus/scripts/verify_corpus.py
```

Após obter o modelo OCR em `corpus/.cache/tessdata/`, a conversão pode rodar offline, sem as opções `--download` e `--download-ocr`. Para usar outro diretório, informar `--tessdata /caminho/tessdata`. O modelo esperado tem SHA-256 `c4932b937207a9514b7514d518b931a99938c02a28a5a5a553f8599ed58b7deb`; se o endereço remoto mudar de conteúdo, o processo falha em vez de usar silenciosamente outro modelo. O ambiente e o cache estão ignorados pelo Git.

Para converter somente uma fonte:

```bash
corpus/.venv/bin/python corpus/scripts/convert_pdfs.py \
  --source protocolos-guia-alimentar-fasciculo1-2021 --overwrite
```

Sem `--overwrite`, saídas existentes são recusadas. Com essa opção, apenas Markdown e relatório da fonte selecionada são regenerados; **não a utilize sobre revisão manual ainda não preservada**. Originais existentes nunca são substituídos; divergência de hash exige investigar a edição e atualizar conscientemente o catálogo. O script não modifica o manifesto nem aprova fontes. Novos ajustes devem ficar em `scripts/config/` ou `scripts/ajustes/`, para sobreviver à regeneração.

Imagens de conferência são renderizadas apenas em diretório temporário fora do repositório. O conversor não exporta imagens; os links `#page=N` permitem consultar figuras e diagramas no PDF original.

## Método e rastreabilidade

1. Verificar assinatura PDF, integridade por SHA-256, quantidade de páginas e correspondência dos ajustes com o original.
2. Extrair todas as páginas com PyMuPDF Layout, mantendo cabeçalhos, rodapés e texto em figuras; sem exportar PNGs. Gerar títulos, parágrafos, listas e tabelas; sem resumir ou produzir orientações novas.
3. Sinalizar páginas com menos de 150 caracteres nativos. A inspeção visual distingue páginas de fotografia/transição de texto que precisa de OCR. As decisões destes dois PDFs estão nas configurações. Em novos documentos, páginas esparsas sem decisão explícita passam por OCR integral e recebem aviso de revisão.
4. Aplicar OCR em regiões delimitadas quando há texto visual ausente da camada nativa. Resultados auxiliares imprecisos ficam no relatório, sem se misturar às orientações. O selo da capa do Guia foi transcrito literalmente após falha do OCR, com registro explícito.
5. Aplicar correções pontuais vinculadas ao hash do PDF. Substituições estritas falham se o trecho esperado mudar. As páginas recompostas ficam em `scripts/ajustes/`, e o link da página leva ao PDF original para conferência. Ajustes de estrutura não implicam revisão humana concluída.
6. Acrescentar `<!-- PDF_PAGE: N -->`, âncora `pagina-pdf-NNN` e link ao original em cada página. Notas editoriais são identificadas como notas de conversão.
7. Produzir relatório com OCR bruto, avisos, diferenças lexicais, ajustes, hashes de scripts/configurações/arquivos e versões das ferramentas. Só gravar os derivados após concluir todas as páginas da fonte.

A comparação lexical conta palavras da camada nativa que não aparecem no texto extraído e sinaliza cobertura inferior a 98%. **Esse limiar é apenas diagnóstico**, não critério de aprovação. Duplicações ocultas no PDF, palavras partidas, mudanças de caixa e rótulos compartilhados em tabelas produzem falsos alertas; cobertura alta também não prova ordem, relações ou fidelidade semântica. Toda diferença fica registrada no JSON, inclusive abaixo do limiar.

## Conferência amostral e limitações

Amostra conferida pelo assistente contra páginas renderizadas; não é revisão humana integral. As páginas abaixo são físicas, sem descontar capas.

| Documento / páginas | Verificação e resultado |
|---|---|
| Guia, 1 e 3 | Capa, edição e licença identificadas. Selo sem texto nativo teve OCR sem resultado útil; texto literal incluído por transcrição pontual e imagem disponível no PDF original. |
| Guia, 51 | Dois blocos de orientação e parágrafos confrontados com a imagem; conteúdo textual preservado na amostra. |
| Guia, 52 | A extração inicial misturava rótulos do diagrama. Recompostos os três grupos de alimentos em tabelas, com link à página original para conferir as correspondências. |
| Guia, 148 | Conferidas as três colunas e as sete linhas da tabela de participantes/contribuições. Totais **436** usuários e **3125** contribuições preservados; capitalização automática de versaletes difere da aparência do original. |
| Fascículo, 3 e 7 | Licença e Quadro 1 conferidos. Preservadas três colunas e quatro grupos de alimentos; corrigidos espaços indevidos entre palavras. |
| Fascículo, 16–18 | Título, sequência de cinco instruções, opções do formulário e ramos SIM/NÃO do fluxograma conferidos. O extrator inicial duplicava números e perdia opções; transcrições pontuais corrigem esses casos. As setas e a geometria original permanecem no PDF original. |
| Fascículo, 19 e 22 | Conferidos títulos e as orientações da amostra; a faixa **6 a 12 horas** da página 19 foi preservada. Corrigidas ordem dos títulos e marcas de tachado produzidas por barras decorativas. |

Limitações registradas para revisão:

- **Guia: páginas 1, 3, 4, 52, 148 e 158.** Selo/contracapa, ordem dos créditos em colunas, continuidade do sumário, diagrama e capitalização da tabela. O OCR dos logotipos da página 158 não é fiel; consultar imagem/PDF.
- **Fascículo: páginas 3, 4, 7, 8, 16–24 e 28.** Créditos, sumário, tabelas, títulos, fluxograma e elementos gráficos. A miniatura da capa na página 8 e logotipos da página 28 não tiveram transcrição OCR confiável. Na página 24, palavras partidas da camada nativa produzem alertas que precisam ser conferidos no original.
- Fotografias, marcas, códigos de barras e a disposição das figuras continuam preservados nos PDFs originais, sem exportação para PNG ou descrição semântica gerada. Selos curvos e letras muito pequenas não têm transcrição automática integral. A estrutura hierárquica de títulos e a ordem em páginas complexas são inferidas e exigem revisão.
- Os créditos públicos das publicações foram mantidos. A separação de dados pessoais se refere aos usuários do CULTIVA, não à supressão de atribuição bibliográfica.
- O Fascículo é destinado à orientação por profissionais. Preservar seu conteúdo documental não autoriza o aplicativo a executar prescrições ou protocolos individualizados.

Os relatórios mantêm esses resultados desfavoráveis e os alertas de cobertura. A conclusão da conversão não demonstra adequação do corpus para uso pelo produto.

## Como incluir outro documento

1. Obter o PDF de origem verificável; manter seus bytes em `nutricao/originais/`, com nome que identifique a edição. Conferir a licença no próprio documento e registrar a página da evidência; usar `pendente` quando desconhecida.
2. Adicionar uma entrada em `manifest.yaml`, reaproveitando os campos existentes. Informar `id`, `title`, `institutions`, `year`, `edition`, `version`, `source`, `license`, `original_path`, `markdown_path` e `report_path`; registrar `sha256` e `pdf_pages` após inspeção. Usar `review_status: pendente` e `approval_status: pendente`. Não copiar a licença das fontes atuais por suposição.
3. Se o arquivo estiver ausente e houver autorização de obtenção, preencher `download_url` para usar `--download`. A assinatura PDF impede aceitar uma página HTML de login como documento.
4. Executar a conversão com `--source ID`. Inspecionar os alertas de pouco texto e os layouts mistos: a presença de texto nativo não exclui texto dentro de imagens. Adicionar, quando necessário, `conversion_config` seguindo os exemplos e vinculando o arquivo ao SHA-256 do PDF.
5. Conferir páginas com OCR, tabelas, unidades, referências e colunas. Registrar perdas por página; manter ajustes literais reproduzíveis e pendências explícitas. Aprovação científica e análise de uso/licença são decisões separadas da extração.
