# Contexto do projeto CULTIVA

Consulta documental realizada em **03/11/2026**, na branch `main` de [Documentacao-Cultiva](https://github.com/Cultiva-Challenge-2-Residencia-IA/Documentacao-Cultiva). Este arquivo resume o contexto para trabalhar no repositório de implementação; regras e requisitos devem ser conferidos nos documentos originais. Todos os documentos listados abaixo foram acessados nesta consulta.

## Produto e limites

O CULTIVA é um projeto da Residência em Inteligência Artificial que apoia jovens adultos e estudantes (18+) na construção de hábitos e em decisões simples e sustentáveis. Reúne **Nutrição, Saúde Física e Estudos**, com um núcleo de registros, metas e resumos. Está alinhado aos ODS 3 (Saúde e Bem-Estar) e 4 (Educação de Qualidade).

O MVP prevê o fluxo registrar, resumir e recomendar nas três áreas, começando pelo protótipo de uma aba. A vitrine de profissionais é classificada como desejável. Saúde Mental, acompanhamento de alunos/pacientes por profissionais e motivação com amigos estão no backlog, fora do escopo atual.

A IA tem finalidade educativa e organizacional: não diagnostica, não prescreve dietas, treinos terapêuticos, medicamentos ou suplementos, nem substitui profissionais (RN01–RN03, RF-IA02). Respostas explicativas precisam citar fontes aprovadas; sem evidência confiável, devem reconhecer a falta de resposta (RN04, RN16, RN17, RF-IA01). O produto prevê tom acolhedor, distinção entre registros e estimativas, detecção prioritária de risco e confirmação antes de salvar interpretações de foto, áudio ou PDF. Em Nutrição, estimativas de porções e nutrientes devem apresentar faixas e incerteza, sem metas calóricas (RF-IA11).

## Documentação original

| Documento | Referência |
|---|---|
| Visão geral, público e escopo | [docs/projeto/index.md](https://github.com/Cultiva-Challenge-2-Residencia-IA/Documentacao-Cultiva/blob/main/docs/projeto/index.md) |
| Regras de negócio | [docs/regras-de-negocio.md](https://github.com/Cultiva-Challenge-2-Residencia-IA/Documentacao-Cultiva/blob/main/docs/regras-de-negocio.md) |
| Organização e situação dos requisitos | [docs/requisitos/index.md](https://github.com/Cultiva-Challenge-2-Residencia-IA/Documentacao-Cultiva/blob/main/docs/requisitos/index.md) |
| Funcionalidades convencionais | [docs/requisitos/funcionais.md](https://github.com/Cultiva-Challenge-2-Residencia-IA/Documentacao-Cultiva/blob/main/docs/requisitos/funcionais.md) |
| Funcionalidades de IA | [docs/requisitos/ia.md](https://github.com/Cultiva-Challenge-2-Residencia-IA/Documentacao-Cultiva/blob/main/docs/requisitos/ia.md) |
| Qualidade, segurança e privacidade | [docs/requisitos/nao-funcionais.md](https://github.com/Cultiva-Challenge-2-Residencia-IA/Documentacao-Cultiva/blob/main/docs/requisitos/nao-funcionais.md) |
| Escopo futuro | [docs/requisitos/backlog.md](https://github.com/Cultiva-Challenge-2-Residencia-IA/Documentacao-Cultiva/blob/main/docs/requisitos/backlog.md) |
| Arquitetura de IA — proposta provisória | [docs/arquitetura.md](https://github.com/Cultiva-Challenge-2-Residencia-IA/Documentacao-Cultiva/blob/main/docs/arquitetura.md) |
| Decisões em aberto | [docs/pendencias.md](https://github.com/Cultiva-Challenge-2-Residencia-IA/Documentacao-Cultiva/blob/main/docs/pendencias.md) |

## Estado das decisões e das evidências

| Classificação | Como identificar e registrar |
|---|---|
| Requisito aprovado | Exige evidência explícita de aprovação, com referência à decisão, responsável e data quando disponíveis. Não inferir aprovação pela prioridade ou pela existência de um ID. |
| Requisito documentado, aprovação não confirmada | Comportamento descrito nos documentos, sem confirmação de aprovação identificada na consulta. O índice de requisitos adota a versão refatorada, mas ainda pede confirmação de que ela substitui a original; isso não demonstra rejeição. |
| Proposta técnica | Solução candidata para atender requisitos. A arquitetura é provisória; os diretórios e campos adicionais de metadados sugeridos neste contexto são convenções locais desta etapa, sem equivaler a uma arquitetura ou esquema formalmente aprovado pela equipe. |
| Hipótese | Afirmação ainda a testar, como a expectativa de que o fluxo integrado melhore a adesão ou de que vários agentes tragam benefício frente a uma solução mais simples. Registrar evidência necessária e condição que poderia contrariá-la. |
| Implementação ou resultado observado | Evidência do que existe ou foi medido, com referência a arquivos ou a execução reproduzível. Não comprova, por si só, aprovação, eficácia geral ou atendimento a todos os requisitos. |

Os comportamentos resumidos neste arquivo são requisitos documentados; esta consulta não confirmou sua aprovação formal. Preservar os limites de atuação descritos enquanto essa confirmação é buscada. Avaliações devem confrontar também decisões anteriores, apresentar inconsistências e alternativas com evidências e impactos, e aceitar conclusões desfavoráveis ao projeto. Registrar critérios antes das comparações, método, versões, amostra e limitações; manter visíveis falhas e resultados negativos, sem selecionar apenas casos favoráveis ou alterar métricas para encobri-los.

## Arquitetura proposta e estado local

A arquitetura publicada é explicitamente uma **proposta inicial e provisória, ainda não validada pela equipe**. Ela descreve RAG restrito a fontes aprovadas, agentes por área, contexto mínimo entre agentes, sincronização nos resumos, guardrails, rastreabilidade, avaliação com golden set e observabilidade. Esses elementos não comprovam implementação nem encerram as decisões de tecnologia. Valores marcados como proposta nos requisitos também dependem de calibração.

Na inspeção local, o README apresenta o produto e a árvore contém:

- `src/`: placeholders para API, agentes, RAG, broker de contexto e guardrails;
- `corpus/manifest.yaml`: catálogo inicial com `version: 1` e `sources: []`; `corpus/scripts/` contém apenas placeholder;
- `eval/`: placeholders de golden set (`dev` e `test`) e execuções;
- `docs/`: espaços para ADRs, RIPD e rubrica, além deste contexto;
- `infra/`, `notebooks/eda/` e `specs/`: placeholders.

Não foram encontrados aplicação executável, dependências ou suíte de testes configurada. A presença dessas pastas indica organização inicial, sem atestar funcionalidades prontas.

### Avaliação crítica inicial

Esta avaliação é documental e estrutural; não houve ensaio de uma aplicação em execução.

- **Falta de evidência empírica.** `src/` e `eval/golden/` contêm placeholders, e [`corpus/manifest.yaml`](../corpus/manifest.yaml) tem `sources: []`. Isso impede confirmar qualidade das respostas, cobertura, segurança, latência e custo; não é uma falha observada em execução. **Próxima verificação proposta:** preparar o corpus revisado e casos de avaliação antes de afirmar viabilidade ou atendimento aos critérios documentados.
- **Presença de citação não demonstra fundamentação.** RF-IA01 exige fontes nas respostas; RNF27 exige afirmações sustentadas, verificadas em amostra humana. A própria [arquitetura, em “Limitações conhecidas”](https://github.com/Cultiva-Challenge-2-Residencia-IA/Documentacao-Cultiva/blob/main/docs/arquitetura.md#qualidade-contínua-llmops), reconhece que ROUGE sozinho não detecta afirmações sem sustentação ou prescrição disfarçada. **Impacto potencial:** uma saída pode ter citação e boa sobreposição textual sem atender a fundamentação ou aos limites de atuação. **Alternativa proposta:** avaliar separadamente presença/validade da referência, sustentação das afirmações e conteúdo prescritivo, com casos adversariais e revisão humana. Ainda não há resultado que comprove a suficiência dos gates propostos.
- **Benefício da complexidade ainda é hipótese.** A arquitetura propõe múltiplos agentes e sincronização, enquanto RF-IA06 orienta começar por uma aba. Isso não é uma contradição: a necessidade da composição completa nesta etapa continua sem demonstração. **Impactos potenciais:** mais coordenação, custo e latência. **Alternativa proposta:** comparar um fluxo de Nutrição com recuperação de fontes e guardrails contra a composição mais complexa, usando os mesmos casos e critérios de qualidade, segurança, custo e latência. A solução simples também precisa ser avaliada; aceitar simplificar ou retirar componentes se o benefício não se confirmar.
- **Revisão editorial não resolve a aprovação da fonte.** A convenção local usa um único `approval_status` (`pendente` ou `aprovado`) para a elegibilidade da fonte (decisão de 06/11/2026; veja `corpus/README.md`), e os critérios de aprovação da arquitetura permanecem pendentes. **Impacto potencial:** confundir texto revisado com fonte autorizada para uso técnico. **Encaminhamento proposto:** manter verificável a decisão de elegibilidade, com critério aplicado, responsável e data quando definidos; sem essa evidência, a aprovação continua pendente. Nenhum aprovador ou resultado de revisão foi presumido.

## Etapa atual: preparar o corpus de Nutrição

A prioridade atual é selecionar, catalogar e revisar fontes científicas de **Nutrição**, separando os documentos originais das versões Markdown revisadas. Esta tarefa estabelece orientações; não adiciona fontes, converte documentos nem implementa ingestão ou RAG.

Convenção para as próximas inclusões (os diretórios de documentos ainda não foram criados):

```text
corpus/
  manifest.yaml
  nutricao/
    originais/<id>/<versao>/documento.<extensao>
    markdown/<id>/<versao>/documento.md
  scripts/
```

- **Originais:** preservar o arquivo obtido da fonte, em seu formato original, sem substituí-lo pelo texto convertido. Uma nova edição deve manter identificável a edição anterior.
- **Markdown revisado:** manter o mesmo identificador e versão do original; conferir fidelidade do texto, tabelas, unidades, notas e referências. Identificar ajustes editoriais e manter referências a páginas ou seções para permitir conferência e citação. Conversões ainda não revisadas são rascunhos e não devem ser apresentadas como versões revisadas.
- **Fluxo:** verificar origem e condições de uso → cadastrar a fonte e seu status → preservar o original → converter e revisar → registrar o Markdown e a conclusão da revisão. Disponibilidade na web ou em um portal aprovado não determina a licença de cada documento.
- **Elegibilidade:** só considerar para uso técnico fontes aprovadas, com licença compatível, metadados completos e revisão concluída. Revisão editorial não substitui aprovação científica da fonte.

### Catálogo e rastreabilidade

[`corpus/manifest.yaml`](../corpus/manifest.yaml) permanece o catálogo das fontes e foi mantido sem alterações nesta tarefa. Preserve sua estrutura `version: 1` e lista `sources`, reaproveitando os campos do exemplo existente. Não há fontes cadastradas; não preencher a lista com exemplos fictícios.

Para os futuros registros em `sources`, adote os seguintes metadados. Os campos adicionais são uma convenção documental local, ainda sem validador implementado:

| Campo | Orientação |
|---|---|
| `id` | Identificador estável da fonte, reaproveitado na organização dos arquivos. |
| `source` | Origem verificável: URL oficial, DOI ou referência que permita localizar o documento. |
| `license` | Licença ou condições de uso verificadas na origem; se desconhecidas, registrar `pendente` e não liberar o uso. |
| `version` | Edição, revisão ou data da fonte; se não houver versão declarada, registrar a data de acesso e essa ausência explicitamente. Não confundir com a versão do formato do manifesto. |
| `approval_status` | Campo adicional: `pendente` ou `aprovado`. `aprovado` indica que a fonte foi conferida e pode alimentar o RAG; a licença não entra nessa decisão. |
| `original_path` | Campo adicional: caminho relativo à raiz do repositório para o original preservado. |
| `markdown_path` | Campo adicional: caminho relativo à raiz para o Markdown revisado; deixar ausente enquanto não existir. |

Registre junto ao Markdown o responsável, a data e as observações da revisão, incluindo limitações e ajustes editoriais. Lacunas de origem, licença ou versão devem permanecer visíveis e impedir a liberação até serem resolvidas. Não criar um catálogo paralelo `sources.yaml`: esse nome aparece na arquitetura provisória, cujo esquema continua pendente; o catálogo adotado neste repositório é o manifesto existente.

### Licenças e aceite de risco (06/11/2026)

A equipe decidiu manter no repositório as cópias e os derivados de todas as fontes do corpus, inclusive as de licença ausente ou ambígua, **assumindo o risco**, porque o CULTIVA é um **projeto de aprendizado sem fins lucrativos**. Isso não é licença nem parecer jurídico, e não aprova nenhuma fonte (revisão e aprovação seguem pendentes). A decisão, a justificativa, as condições (atribuição, retirada imediata a pedido do titular, sem uso comercial) e os gatilhos de reavaliação (como a vitrine paga, RN12) estão em [`corpus/README.md`](../corpus/README.md), seção "Decisão sobre licenças e uso das fontes".

### Separação de dados pessoais

O corpus científico é a base de referências aprovadas, **separada dos dados pessoais dos usuários**. Perfis, metas individuais, registros de hábitos e saúde, conversas, fotos, áudios e PDFs enviados por usuários pertencem ao domínio de dados pessoais e não devem ser incluídos em `corpus/`, no manifesto ou nos derivados do corpus, como chunks, embeddings e índices científicos. Um PDF recebido de usuário não se torna fonte científica por ter sido convertido para Markdown.

O núcleo integrado de registros previsto em RN06 se refere às informações do usuário; ele não autoriza misturá-las com o corpus. O tratamento desses dados deve seguir os requisitos documentados de consentimento, minimização, isolamento entre usuários, exportação e exclusão (RF-A16–RF-A18, RNF05, RNF12, RNF21, RNF25). Esta orientação não define uma solução de armazenamento nem implementa esses controles.

## Pendências encontradas

- **Corpus local:** selecionar e aprovar as primeiras fontes de Nutrição, verificar licenças e versões, obter originais e produzir Markdown revisado. O catálogo ainda está vazio.
- **Curadoria e arquitetura:** definir critérios de confiabilidade e aprovação, formalizar o esquema de metadados e a rotina de reindexação; validar a arquitetura e escolher provedores de modelo e embeddings, respeitando a restrição de uso dos dados para treino. Grafo de conhecimento e análise causal seguem fora do MVP na proposta.
- **Requisitos:** confirmar com a equipe que a versão refatorada (`RF-A`/`RF-IA`) substitui a lista original; uniformizar a RN03 e calibrar valores marcados como proposta.
- **Produto e operação:** definir limite de cliques, interações/créditos e custo por usuário, plataformas-alvo, canal de lembretes, escopo de áudio, critérios da vitrine e modelo de assinatura dos profissionais; registrar as decisões P1 das Guiding Questions e validar problema, núcleo comum e métricas iniciais.

As pendências acima resumem a visão geral, a arquitetura e o documento de pendências consultados. Devem continuar identificadas como decisões em aberto, sem transformar propostas em compromissos de implementação.
