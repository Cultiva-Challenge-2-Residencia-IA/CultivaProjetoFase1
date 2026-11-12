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

Uma busca dirigida suplementar localizou a **Diretriz Brasileira de Hipertensão Arterial – 2025**, DOI [10.36660/abc.20250624](https://doi.org/10.36660/abc.20250624), publicada nos *Arquivos Brasileiros de Cardiologia* e disponível na [SciELO](https://www.scielo.br/j/abc/a/BXT7Vk4B9VKQnJFsJhgJ4Hn/?lang=pt). A diretriz declara autoria institucional SBC/SBH/SBN, acesso aberto CC BY e apresenta seção de declarações de conflitos; menciona padrão DASH e ressalva de potássio em DRC. O número de resultados da consulta suplementar não foi capturado, então esta referência não compõe contagens do fluxo. Confirmar licença exata e texto integral, método, vigência, conflitos individuais e qualidade antes de qualquer proposta de inclusão. É pista candidata, não fonte aprovada.

## Limitações e próximo passo

- Triagem preliminar por um avaliador; não é triagem formal independente nem avaliação de qualidade.
- O filtro por tipo de publicação e Adult[Mesh] pode excluir guideline/revisão recente ainda não indexada; consultar SciELO e portais oficiais e repetir busca sem esses filtros de forma documentada.
- A busca ampla teve 765 resultados, mas só os primeiros 10 foram recuperados; não houve triagem integral dessa consulta.
- Nenhum texto integral dos seis candidatos foi avaliado nesta execução. Não se pode afirmar que exista fonte elegível até resolver acesso, escopo, duplicação, vigência, qualidade, conflitos e licença.
- Próximo passo: recuperar os seis textos, avaliar pertinência por PICO/pergunta e preencher decisão individual. Para a diretriz brasileira, executar AGREE II com dois avaliadores se a equipe aprovar o método e houver avaliadores; manter checklist existente e sem corte de nota inventado.
- Caso futura consulta em BVS/LILACS ou sociedade seja usada, registrar execução separada e confirmar previamente a condição do RN16.
