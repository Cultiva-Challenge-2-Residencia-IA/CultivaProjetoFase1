# Busca piloto: DASH e hipertensão em adultos (PubMed)

**ID:** BUSCA-2026-11-12-PUBMED-DASH-HTA

**Protocolo:** proposta local `corpus/protocolo-busca-selecao.md`

**Data:** 2026-11-12 (UTC; execução via NCBI E-utilities)

**Finalidade:** demonstrar o registro com uma busca real sobre lacuna de hipertensão/DASH. Não é revisão sistemática e não aprova fontes.

## Estratégias e resultados

As consultas foram reexecutadas em 2026-11-12 no NCBI E-utilities com o intervalo exato de publicação `2016/11/12:2026/11/12[dp]`, conforme o limite móvel de 10 anos. A busca exploratória ampla não foi triada e não entra no fluxograma focal. Na execução focada, o NCBI retornou aviso de que ignorou o parâmetro de ordenação solicitado (`sort=pub+date`); a ordenação não deve ser interpretada como recente-primeiro.

| Execução | String exata | Filtros | Resultado |
|---|---|---|---:|
| Exploratória, fora do fluxo | `("Dietary Approaches To Stop Hypertension"[Mesh] OR DASH[tiab]) AND ("Hypertension"[Mesh] OR hypertens*[tiab]) AND "Adult"[Mesh] AND 2016/11/12:2026/11/12[dp] AND (english[lang] OR portuguese[lang])` | Adult, 12/11/2016–12/11/2026, inglês/português | 765; primeiros 10 recuperados para inspeção, sem triagem sistemática |
| Focada, fluxo reportado abaixo | `("Dietary Approaches To Stop Hypertension"[Mesh] OR DASH[tiab]) AND "Hypertension"[Mesh] AND "Adult"[Mesh] AND (Guideline[pt] OR Practice Guideline[pt] OR Systematic Review[pt]) AND 2016/11/12:2026/11/12[dp] AND (english[lang] OR portuguese[lang])` | Adult, guideline/practice guideline/revisão sistemática, 12/11/2016–12/11/2026, inglês/português | 12; 12 retornados |

Descritores usados: MeSH `Dietary Approaches To Stop Hypertension`, `Hypertension`, `Adult`; termos livres `DASH`, `hypertens*`. A tradução de vocabulário foi feita pelo PubMed/MeSH em 2026-11-12; a estratégia não incluiu DeCS nem população com DRC. Não houve filtro `free full text`. Essa busca focada pode perder documentos não indexados nos tipos de publicação selecionados; a busca ampla e SciELO/portais oficiais são complementos necessários. A revisão [PMID 26773016](https://pubmed.ncbi.nlm.nih.gov/26773016/) apareceu na extração anterior por anos-calendário, mas foi removida do resultado elegível: sua data de publicação é 15/01/2016, anterior ao corte de 12/11/2016. Ela não integra os 12 resultados da consulta refeita.

## Fluxo preliminar

| Etapa | n | Nota |
|---|---:|---|
| Registros encontrados na consulta focada PubMed | 12 | Retorno NCBI E-utilities em 12/11/2026 com data inicial e final exatas; IDs listados abaixo |
| Duplicatas dentro desta execução | 0 | Uma única base; cruzamento com outras bases ainda não realizado |
| Título/resumo triados | 12 | Triagem preliminar assistida por leitura de metadados/resumo; um avaliador |
| Excluídos em título/resumo | 6 | Motivos abaixo |
| Avançaram para busca e leitura de texto integral | 6 | Candidatos, não incluídos |
| Texto integral obtido e avaliado | 0 | Pendente |
| Excluídos após texto integral | 0 | Nenhum avaliado nesta etapa |
| Incluídos no corpus/manifesto | 0 | Nenhuma aprovação ou alteração do manifesto |

### Avançam para texto integral (6)

| PMID | Referência resumida | Justificativa preliminar |
|---|---|---|
| [42652274](https://pubmed.ncbi.nlm.nih.gov/42652274/) | Revisão sobre atividades recreativas/dieta em hipertensão ou hiperglicemia em adultos de países de baixa e média renda | Verificar relação direta com DASH, elegibilidade e população no texto integral |
| [40326569](https://pubmed.ncbi.nlm.nih.gov/40326569/) | Revisão Cochrane (2025) de DASH para prevenção primária/secundária de doença cardiovascular | DASH diretamente pertinente; pressão arterial aparece como desfecho secundário |
| [38804177](https://pubmed.ncbi.nlm.nih.gov/38804177/) | Revisão sistemática (2024) de DASH com restrição de sódio e pressão arterial | Pergunta diretamente pertinente |
| [34353704](https://pubmed.ncbi.nlm.nih.gov/34353704/) | Revisão sistemática/metanálise (2021) de DASH e fatores metabólicos em doenças crônicas | Verificar desfechos, população e aplicabilidade |
| [32330233](https://pubmed.ncbi.nlm.nih.gov/32330233/) | Revisão sistemática/metanálise (2020) de DASH e pressão arterial em adultos com/sem hipertensão | Pergunta diretamente pertinente |
| [32259613](https://pubmed.ncbi.nlm.nih.gov/32259613/) | Revisão sistemática/metanálise (2020) de dietas e pressão arterial em pessoas com DM2, inclui DASH | Verificar resultado específico e população adulta |

### Registro removido pelo corte temporal

| PMID | Data | Decisão |
|---|---|---|
| [26773016](https://pubmed.ncbi.nlm.nih.gov/26773016/) | 15/01/2016 | Excluído antes da triagem temática: publicação anterior a 12/11/2016. Constava na consulta antiga, limitada por ano-calendário, e não faz parte dos 12 registros da consulta refeita. |

### Excluídos por título/resumo (6)

| PMID | Razão primária preliminar |
|---|---|
| [40525605](https://pubmed.ncbi.nlm.nih.gov/40525605/) | Intervenção multimodal de promoção de saúde, sem intervenção DASH especificamente pertinente |
| [40268568](https://pubmed.ncbi.nlm.nih.gov/40268568/) | DASH e perfil lipídico, sem desfecho de pressão arterial pertinente à busca |
| [34117485](https://pubmed.ncbi.nlm.nih.gov/34117485/) | Razão urinária sódio:potássio; sem avaliação de intervenção/padrão DASH |
| [32063407](https://pubmed.ncbi.nlm.nih.gov/32063407/) | Desfecho de câncer colorretal, fora da pergunta de pressão arterial |
| [31669002](https://pubmed.ncbi.nlm.nih.gov/31669002/) | Risco de desenvolvimento de DRC; não trata manejo de pressão/potássio em DRC existente |
| [31245918](https://pubmed.ncbi.nlm.nih.gov/31245918/) | Revisão de sal com subanálise DASH, não revisão de intervenção/padrão DASH pertinente; manter como pista bibliográfica separada se necessário |

Motivos são preliminares, baseados em metadados e resumos; podem ser corrigidos após texto integral. A lista não representa avaliação de risco de viés ou certeza GRADE.

## Busca suplementar SciELO (fora da contagem PubMed)

Uma busca dirigida suplementar localizou a **Diretriz Brasileira de Hipertensão Arterial – 2025**, DOI [10.36660/abc.20250624](https://doi.org/10.36660/abc.20250624), publicada nos *Arquivos Brasileiros de Cardiologia* e disponível na [SciELO](https://www.scielo.br/j/abc/a/BXT7Vk4B9VKQnJFsJhgJ4Hn/?lang=pt). A diretriz declara autoria institucional SBC/SBH/SBN, acesso aberto CC BY e apresenta seção de declarações de conflitos; menciona padrão DASH e ressalva de potássio em DRC. O número de resultados da consulta suplementar não foi capturado, então esta referência não compõe contagens do fluxo. Confirmar a referência e avaliar texto integral, método, vigência, conflitos e qualidade antes de qualquer proposta de inclusão; registrar a licença conforme a informação publicada ou como `pendente`, sem tratá-la como critério eliminatório. É pista candidata, não fonte aprovada.

## Limitações e próximo passo

- Triagem preliminar por um avaliador; não é triagem formal independente nem avaliação de qualidade.
- O filtro por tipo de publicação e Adult[Mesh] pode excluir guideline/revisão recente ainda não indexada; consultar SciELO e portais oficiais e repetir busca sem esses filtros de forma documentada.
- A busca ampla teve 765 resultados, mas só os primeiros 10 foram recuperados; não houve triagem integral dessa consulta.
- O fluxo reportado cobre somente a consulta focada, com `Adult[Mesh]` e filtro por tipo de publicação, filtros que o protocolo recomenda não usar como busca única. A busca ampla não foi triada integralmente; SciELO e portais oficiais também não entraram nesse fluxo.
- Nenhum texto integral dos seis candidatos foi avaliado nesta execução. Ainda não há decisão de inclusão; verificar escopo, duplicação, vigência, qualidade e conflitos. Registrar a licença real ou `pendente`, sem bloqueio por licença no escopo acadêmico coberto pelo aceite de risco.
- Próximo passo: recuperar os seis textos, avaliar pertinência por PICO/pergunta e preencher decisão individual. Para a diretriz brasileira, executar AGREE II com dois avaliadores se a equipe aprovar o método e houver avaliadores; manter checklist existente e sem corte de nota inventado.
- Caso futura consulta em BVS/LILACS ou sociedade seja usada, registrar execução separada e confirmar previamente a condição do RN16.

## Avaliação dos candidatos (19/11/2026)

**Quem e como:** MatheusSales2773, com assistência de IA (Claude Code). Os metadados vêm do PubMed (E-utilities) e do conversor de IDs do PMC; o texto integral, do PMC e da SciELO quando disponível em acesso aberto. **Um avaliador.** Esta avaliação **não inclui nada no corpus**: a inclusão exige decisão humana registrada e a aprovação da fonte (`corpus/README.md`), e o manifesto não foi alterado.

**Correção de identificadores:** os PMCID e DOI corretos vêm do conversor de IDs do PMC. Uma leitura do XML do PubMed que percorra todo o documento mistura os identificadores das **referências** dos artigos.

| Candidato | Tipo e acesso | Pertinência para a lacuna (DASH, potássio, DRC) | Conflito de interesse | Situação proposta |
|---|---|---|---|---|
| **Diretriz Brasileira de Hipertensão Arterial – 2025** (SBC/SBH/SBN), *Arq Bras Cardiol*, DOI [10.36660/abc.20250624](https://doi.org/10.36660/abc.20250624) | Diretriz vigente, em português; acesso aberto na SciELO, licença Creative Commons Attribution; texto integral consultado (HTML) | **Alta.** Tem seção de ingestão de sódio e potássio e capítulo de hipertensão com doença renal crônica. Recomendações com força e certeza: aumento do potássio dietético para reduzir a PA, **exceto em pacientes com DRC** (forte, alta); dieta DASH e atividade física para reduzir PA e mortalidade (forte, alta) | Declarado autor por autor; vários autores relatam relação com a indústria farmacêutica (eventos e consultorias, por exemplo Novo Nordisk, EMS, Biolab), sem relação evidente com recomendações dietéticas | **Prioridade 1 para inclusão.** Seguir "Como incluir outro documento", com conversão e aprovação. Publicada na SciELO, que está no RN16; a autoria por sociedades depende da decisão 1 da #47. Avaliar AGREE II se houver dois avaliadores (decisão 3) |
| PMID [40326569](https://pubmed.ncbi.nlm.nih.gov/40326569/): Cochrane (2025), DASH para prevenção primária e secundária de doença cardiovascular; PMC12053460 | Revisão sistemática com metanálise; copyright Cochrane/Wiley; por E-utilities, o PMC só devolveu o resumo | **Média.** Alta qualidade metodológica (GRADE por desfecho), mas 5 ECR (1.397 participantes, EUA e Polônia), todos em prevenção primária; desfechos duros com certeza baixa ou muito baixa. A PA é desfecho secundário | Declarado; sem conflito relevante no resumo | **Candidato complementar.** Útil para mostrar o limite da evidência ("não há prova de que DASH previna infarto"); texto integral e licença a confirmar |
| PMID [32330233](https://pubmed.ncbi.nlm.nih.gov/32330233/): *Adv Nutr* (2020), DASH e PA em adultos com e sem hipertensão; PMC7490167 | Revisão sistemática com metanálise de 30 ECR (5.545 participantes); modelo de publicação padrão da OUP (não é CC); por E-utilities, o PMC só devolveu o resumo | **Alta para PA.** O efeito do DASH na PA é maior com ingestão de sódio > 2.400 mg/d e em menores de 50 anos | Não informado no resumo do PubMed | **Candidato complementar**, se a diretriz não bastar; texto integral e licença a confirmar |
| PMID [38804177](https://pubmed.ncbi.nlm.nih.gov/38804177/): *Br J Nutr* (2024), DASH com restrição de sódio e PA | Revisão sistemática (PROSPERO CRD42023409996), adultos ≥ 18 anos; "© The Author(s)", provável acesso aberto na Cambridge; fora do PMC; texto integral não obtido | **Alta para sódio + DASH** | "Sem conflitos", declarado | **Retenção pendente**, razão "sem texto integral" nesta execução |
| PMID [42652274](https://pubmed.ncbi.nlm.nih.gov/42652274/): *IJERPH* (2026), atividades recreativas e manejo dietético em hipertensão e hiperglicemia em países de baixa e média renda; PMC13511943 | Revisão sistemática; CC BY; texto integral consultado | **Baixa.** Mistura atividade física e dieta; DASH aparece de forma lateral ("DASH e mediterrânea podem melhorar a PA, mas dependem de adesão"); nenhuma menção ao Brasil | "Sem conflitos", declarado | **Excluir**, razão "desenho/desfecho": não responde diretamente à lacuna |
| PMID [34353704](https://pubmed.ncbi.nlm.nih.gov/34353704/): *NMCD* (2021), DASH e fatores metabólicos em doença crônica | Metanálise de 54 ECR; Elsevier, sem acesso aberto identificado | **Média.** População com doença crônica variada | "Sem conflitos", declarado | **Retenção pendente**, razão "sem texto integral"; baixa prioridade |
| PMID [32259613](https://pubmed.ncbi.nlm.nih.gov/32259613/): *Diabetes Res Clin Pract* (2020), dietas e PA em diabetes tipo 2 | Metanálise de 24 ECR; Elsevier, sem acesso aberto | **Baixa para a lacuna.** População com DM2; DASH é uma entre várias dietas | "Sem conflitos", declarado | **Retenção pendente**, razão "sem texto integral"; baixa prioridade |

**Fluxo atualizado (busca PubMed):** 12 registros → 6 excluídos na triagem → 6 avaliados → **1 excluído** (42652274, desenho/desfecho), **2 complementares** (40326569, 32330233), **3 em retenção pendente sem texto integral** (38804177, 34353704, 32259613) → **0 incluídos**. Fora da contagem PubMed, a busca suplementar na SciELO trouxe a diretriz de 2025 como prioridade 1.

**Próximo passo proposto:** incluir a Diretriz Brasileira de Hipertensão 2025 pelo processo de "Como incluir outro documento", depois das decisões 1 (RN16 e sociedades) e 3 (AGREE II) da #47, com aprovação humana registrada.
