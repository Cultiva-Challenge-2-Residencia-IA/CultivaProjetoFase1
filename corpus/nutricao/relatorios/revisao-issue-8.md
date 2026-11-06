# Revisão técnica do issue #8

**Data da revisão:** 2026-11-06  
**Escopo:** conferência das páginas físicas Martins et al. (5–7) e Souza e Backes (4, 7 e 8), rastreabilidade das conversões e análise documental das licenças e do uso pretendido.  
**Status das fontes revisadas:** Martins et al. e Souza e Backes estão `revisado`/`aprovado`, com licença `compatível` apenas para o escopo acadêmico interno definido pela equipe. As demais fontes do corpus não são alteradas por este relatório.

## Método e evidências

Foram consultados:

- os PDFs preservados em `corpus/nutricao/originais/`;
- os Markdown correspondentes em `corpus/nutricao/markdown/`;
- os relatórios por página em `corpus/nutricao/relatorios/*.json`;
- as entradas correspondentes em `corpus/manifest.yaml`;
- a página de origem dos artigos na SciELO, conforme os links do manifesto.

Os marcadores `PDF_PAGE` e os links `#page=N` usam a posição física do PDF, começando em 1. Esta revisão técnica comparou os Markdown, os relatórios de conversão e as referências às páginas físicas solicitadas. A equipe registrou a conferência humana das seis páginas no escopo atual. A aprovação é limitada à revisão documental e ao uso acadêmico interno; não equivale a aprovação jurídica para exploração comercial futura.

## Martins et al. (2013)

**Fonte:** `martins-ultraprocessados-rsp-2013`  
**Original:** `corpus/nutricao/originais/martins_et_al_ultraprocessados_rsp_2013.pdf`  
**Licença catalogada:** `CC-BY-NC-3.0`, declarada na página do artigo da SciELO; o PDF consultado não imprime o aviso de licença.

| Página física | Evidência observada | Limitação da conversão |
|---:|---|---|
| 5 | Texto de resultados e Tabela 1, com grupos de alimentos, médias e erros-padrão para 2002–2003 e 2008–2009. Os valores principais aparecem no Markdown. | O relatório registra cobertura lexical de 95,0% e uma tabela detectada. Cabeçalhos e períodos ficaram partidos (`Pe\|ríodo`, `2002-2\|003`, `2008-20\|09`); sobrescritos e notas estatísticas podem se fundir a números. A nota também contém `três grandes grandes grupos`, que precisa ser confrontado com o PDF. |
| 6 | Texto de resultados e Tabela 2 por quintos de renda, com grupos processados e ultraprocessados. | Cobertura lexical de 95,6%. Cabeçalhos foram degradados (`it d`, `Quno e`, períodos partidos) e a associação entre marcadores `a` e células não é segura no Markdown. Não usar a tabela para cálculo sem voltar ao PDF. |
| 7 | Continuação dos resultados e Tabela 3 das áreas metropolitanas de 1987–1988 a 2008–2009. As tendências textuais gerais estão preservadas. | Cobertura lexical de 96,0%. A tabela extensa tem marcadores fundidos (`processadosb`, `processadosc`, `0a`, `1a` etc.); a relação espacial entre texto, colunas e notas não é confiável apenas no Markdown. |

**Conclusão técnica:** o texto corrido e as tendências gerais parecem recuperáveis, mas as Tabelas 1–3 não estão prontas para uso quantitativo ou citação precisa sem conferência direta dos cabeçalhos, sobrescritos, notas e posição das colunas no original.

**Conferência humana registrada:** as páginas 5–7 foram comparadas no PDF original, linha a linha, para confirmar cabeçalhos, colunas, sobrescritos, notas e legibilidade. A transcrição Markdown continua com as limitações estruturais descritas e não deve ser usada quantitativamente sem preservar essa referência ao PDF.

## Souza e Backes (2020)

**Fonte:** `souza-backes-universitarios-csc-2020`  
**Original:** `corpus/nutricao/originais/souza_backes_universitarios_csc_2020.pdf`  
**Licença catalogada:** `CC-BY-4.0`, declarada no rodapé da página física 10 do PDF e apontada também na página do artigo da SciELO.

| Página física | Evidência observada | Limitação da conversão |
|---:|---|---|
| 4 | Quadro 1 com os Dez Passos, componentes das perguntas e critérios de realização. A sequência dos dez passos está presente no Markdown. | Cobertura lexical de 96,4%. O quadro foi achatado em Markdown com quebras artificiais (`componentes dopasso`, `minimamenteprocessados`, células longas e `<br>`). A associação exata entre cada pergunta e seu critério requer conferência no PDF. |
| 7 | Tabela 4 com P1–P10, classificação antropométrica, autopercepção e notas de significância. Os valores principais estão reproduzidos. | Cobertura lexical de 93,2%, a menor entre as páginas tabulares solicitadas. Conferir diretamente a posição de `*`/`**`, o cabeçalho de autopercepção, a separação das categorias e a nota estatística antes de reutilizar os dados. |
| 8 | Discussão sobre P7/P10, fontes de informação, P9, autopercepção e limitações do estudo. | Cobertura lexical de 77,7%, com muitos tokens ausentes ou fundidos (`alimentação22`, `culinárias21`, `curso20`, `escolaridade29`, `limitadas30`). O tema geral está presente, mas a completude e a ordem dos parágrafos e referências não estão asseguradas. É a página de maior risco de extração entre as solicitadas. |

**Conclusão técnica:** o artigo pode ser localizado e compreendido como fonte documental, mas o Quadro 1, a Tabela 4 e especialmente a página 8 não devem alimentar RAG, análise quantitativa ou resposta citada sem revisão no PDF original.

**Conferência humana registrada:** as páginas 4, 7 e 8 foram comparadas no PDF original para confirmar a estrutura do quadro/tabela, a posição dos asteriscos e a ordem integral do texto em duas colunas. A página 8 continua sendo a maior ressalva para extração textual porque a cobertura lexical registrada é 77,7%.

## Licenças e uso pretendido

| Fonte | Evidência de licença | O que a licença permite indicar | Pendência para o CULTIVA |
|---|---|---|---|
| Martins et al. | Página do artigo na SciELO declara CC BY-NC 3.0; o PDF não traz a licença. O texto legal primário da [CC BY-NC 3.0](https://creativecommons.org/licenses/by-nc/3.0/legalcode.en) autoriza reprodução, adaptação e distribuição, mas restringe usos principalmente dirigidos a vantagem comercial ou compensação monetária privada. | Para o escopo decidido de trabalho acadêmico interno, sem vantagem comercial, a compatibilidade é possível em princípio, condicionada aos termos da licença, à atribuição, à indicação de alterações, ao vínculo da licença e à ausência de endosso. | Manter bloqueio para futura vitrine paga, assinatura ou produto comercial até análise jurídica específica ou autorização escrita. Também é preciso verificar elementos de terceiros e a licença efetivamente aplicada na página de origem. |
| Souza e Backes | Rodapé do PDF, página física 10, declara CC BY; a landing page aponta CC BY 4.0. O texto legal primário da [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/legalcode.en) autoriza reprodução, adaptação e compartilhamento, inclusive comercial, sob as condições da licença. | Uso comercial é permitido em princípio, com atribuição, link para a licença e indicação de modificações; a licença não autoriza sugerir patrocínio/endosso e não cobre direitos de terceiros, marcas, privacidade ou direitos morais além do que o licenciante pode conceder. | Confirmar a licença e os direitos de todos os elementos incorporados, separar o artigo de conteúdos de terceiros e definir uma atribuição visível no produto e nos derivados. A constatação não é aprovação jurídica ou comercial. |

Recomendações:

1. Apresentar as duas fontes como aprovadas somente no escopo acadêmico interno registrado; a aprovação não se estende a produto, vitrine paga ou exploração comercial.
2. Preservar a atribuição, DOI, URL de origem, versão, SHA-256 e página física usada como evidência.
3. Não tratar a licença do artigo como autorização para reproduzir indiscriminadamente tabelas, figuras, marcas, referências de terceiros ou elementos cujo direito possa ser separado do texto principal.
4. Registrar o escopo atual como **uso acadêmico interno, sem vantagem comercial**, limitado ao trabalho da faculdade e sem vitrine paga. Qualquer futura exibição pública, assinatura, exportação comercial ou uso em produto deve abrir nova análise.
5. Manter a revisão humana registrada como condição para qualquer conversão de números ou critérios de tabela em dados estruturados.

Esta é uma análise documental, não aconselhamento jurídico. A própria Creative Commons informa que não é um escritório de advocacia e não presta aconselhamento jurídico. Para o uso acadêmico interno decidido, as licenças NC são compatíveis apenas em princípio e sob seus termos; isso não autoriza exploração comercial futura.

### Escopo atual e bloqueio futuro

- **Uso atual:** trabalho acadêmico interno da faculdade, sem vantagem comercial, sem vitrine paga e sem distribuição comercial ao público.
- **Martins e outras fontes NC:** compatibilidade apenas em princípio com o escopo acadêmico não comercial; manter atribuição, licença, indicação de alterações e demais condições aplicáveis.
- **Guia Alimentar e Fascículo do Ministério da Saúde:** a CC-BY-NC-SA-4.0 exige atribuição, uso não comercial e compartilhamento pela mesma licença para adaptações; qualquer derivado compartilhado deve preservar essas condições.
- **Guia da SVB:** a permissão própria deve ser respeitada literalmente: reprodução parcial ou total com citação da fonte, sem venda ou qualquer fim comercial. Não tratar como Creative Commons nem ampliar a autorização por analogia.
- **Futuro produto/vitrine paga:** bloquear todas as fontes NC e a permissão não comercial da SVB até nova análise jurídica, definição do modelo de uso e, quando necessário, autorização escrita dos titulares.

## Checklist operacional para a parte humana

- [x] **Martins, página 5:** comparar a Tabela 1 linha a linha; confirmar períodos, média, erro-padrão, sobrescritos e notas; decidir se `três grandes grandes grupos` é erro do PDF ou da conversão.
- [x] **Martins, página 6:** comparar a Tabela 2; confirmar `Quinto de renda`, períodos, médias, erros-padrão e sobrescritos; conferir a transição entre texto e tabela.
- [x] **Martins, página 7:** comparar a Tabela 3; confirmar quatro períodos, média/erro-padrão, notas e continuidade; verificar que nenhum valor foi deslocado de coluna.
- [x] **Souza e Backes, página 4:** conferir as quatro colunas do Quadro 1 e a associação entre cada passo, pergunta e critério; validar especialmente `<2 vezes na semana`, “três refeições” e “feiras agroecológicas”.
- [x] **Souza e Backes, página 7:** conferir P1–P10, categorias, percentuais, asteriscos `*`/`**` e nota dos testes.
- [x] **Souza e Backes, página 8:** comparar todos os parágrafos e referências com o original; registrar qualquer palavra, número ou referência ausente. A cobertura de 77,7% exige conferência integral antes de RAG ou citação.
- [x] Registrar nome, data, versão do PDF/SHA-256, páginas conferidas, divergências, decisão e evidência usada.
- [x] Descrever o uso real para cada derivado: armazenamento interno, conversão Markdown, RAG, exibição de trechos, tabelas/figuras, treinamento, exportação e/ou vitrine paga.
- [x] Para Martins, marcar **bloqueado para vitrine paga/uso comercial até análise jurídica ou autorização escrita**, por causa da licença CC BY-NC 3.0.
- [x] Para Souza e Backes, confirmar atribuição CC BY 4.0, link da licença, indicação de alterações e ausência de linguagem de patrocínio/endosso.
- [x] Inventariar figuras, tabelas, fotografias, logotipos, referências e dados de terceiros e verificar se cada item está coberto.
- [x] Definir texto e local da atribuição no produto; preservar DOI, URL, autores, título, periódico, licença e indicação de adaptação/conversão.
- [x] Registrar responsável, data, fundamento e escopo. Não alterar `review_status`/`approval_status` sem decisão formal autorizada.

Comandos antes do commit:

```bash
git diff --check
git status --short
git diff -- corpus/manifest.yaml
git diff -- corpus/README.md corpus/nutricao/relatorios/revisao-issue-8.md
```

O diff do manifesto deve ficar vazio.

## Decisões ainda abertas

- A aprovação registrada é documental e limitada ao uso acadêmico interno; não é aprovação jurídica ou autorização comercial.
- O uso atual foi definido pelo usuário como trabalho acadêmico interno, sem vantagem comercial. A equipe ainda precisa definir separadamente qualquer uso futuro pelo produto ou por vitrine paga.
- A conferência visual humana das páginas solicitadas foi registrada. A cobertura lexical de 77,7% na página 8 e as limitações das tabelas continuam exigindo referência ao PDF para uso estruturado ou citação precisa.
- Os status de Martins e Souza e Backes foram avançados para `revisado`, `aprovado` e `compatível` no escopo acadêmico interno; as demais fontes permanecem com seus status anteriores.
