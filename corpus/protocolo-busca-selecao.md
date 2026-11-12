# Protocolo de busca e seleção de fontes de Nutrição

**Estado:** proposta operacional desta branch; aprovação formal da equipe não localizada.

**Escopo:** descoberta e seleção bibliográfica de documentos para o corpus científico de Nutrição. Não altera os limites educativos do produto, não autoriza diagnóstico/prescrição e não inclui dados pessoais.

Este protocolo cobre a etapa anterior à checklist de inclusão de [`README.md`](README.md). A aplicação piloto é exploratória e não constitui revisão sistemática publicada. Os registros versionados devem permitir repetir a consulta e entender cada decisão sem reconstruir contagens que não foram anotadas.

## Decisões propostas

| Tema | Escolha operacional | Estado e justificativa |
|---|---|---|
| Canais centrais | PubMed, SciELO e portais oficiais do Ministério da Saúde, como enumerados no pedido como whitelist do RN16 | Requisito documentado no pedido; texto original do RN16 e whitelist exata ainda precisam ser confirmados. Até essa confirmação, não afirmar que outras bases estão formalmente autorizadas. |
| BVS/LILACS | Busca complementar, com base e coleção identificadas separadamente; deduplicar com PubMed/SciELO | Proposta técnica. Usar em produção do corpus somente após conferir compatibilidade com RN16. A BVS é portal/plataforma e LILACS é uma base; registrar qual interface e coleção foram consultadas. |
| Sociedades científicas | Pesquisa complementar em páginas oficiais de sociedades (por exemplo, ABESO, SBME, SBAN, SVB), não whitelist automática | Proposta. Avaliar cada documento por procedência, método, vigência, escopo, conflitos, licença e qualidade. Vínculo institucional isolado não basta. |
| Idiomas | Português e inglês como padrão; espanhol pode ser incluído em busca regional BVS/LILACS quando houver pertinência e capacidade de revisão | Proposta. Registrar idiomas e limitações por busca. Não usar idioma como motivo de exclusão sem registrá-lo. |
| Acesso | Não filtrar por “free full text” na descoberta. Exigir texto integral acessível e licença compatível antes de inclusão técnica | Evita perder registros pertinentes por metadados de acesso incompletos; resumo sozinho serve apenas para triagem, nunca para sustentar resposta do RAG. |
| Data | Para novas buscas, limitar a publicação aos 10 anos imediatamente anteriores à data de execução, com datas inicial e final registradas. Documento mais antigo só entra por uma rota de exceção: norma/diretriz ainda vigente ou referência seminal indispensável, justificada e sinalizada separadamente | Decisão de escopo solicitada nesta tarefa; a exceção evita excluir norma atual só pela idade. A janela não prova vigência nem qualidade. |
| População | Priorizar adultos (18+), avaliados na triagem de título/resumo e texto integral. Não exigir sempre `Adult[Mesh]` na busca | Evita excluir registros recentes ainda não indexados ou estudos de população mista que informem a pergunta adulta. Separar evidência pediátrica e não generalizar para adultos. |
| Tipo de estudo | Não aplicar filtro de tipo como única busca. Priorizar diretriz/norma vigente; depois revisão sistemática/metanálise; depois estudo primário adequado à pergunta. Revisões narrativas servem para contexto e localizar referências | Hierarquia de triagem, não pontuação automática de verdade. Norma tem autoridade regulatória, não necessariamente evidência clínica; registrar ambos os aspectos. |
| Avaliação | Manter checklist atual de procedência, vigência, conflito de interesse, escopo e licença. AGREE II como avaliação complementar de diretrizes clínicas, idealmente por dois avaliadores; sem nota de corte local até decisão explícita. GRADE deve ser registrado quando o documento o reportar, sem reclassificação independente por padrão | Proposta proporcional. AGREE II avalia qualidade de diretrizes (23 itens/seis domínios); GRADE avalia certeza por desfecho/corpo de evidência, não é selo geral de uma fonte. Se só houver um avaliador, declarar limitação e não alegar avaliação dupla. |
| Aplicação retroativa | Fazer auditoria de adequação das 22 fontes atuais (origem, versão/vigência, escopo, COI, licença, qualidade/conversão), mas não reconstruir buscas antigas nem inventar contagens. Aplicar registro completo a buscas novas | Proposta. Preserva rastreabilidade real e permite identificar lacunas. Auditoria não revoga nem ratifica automaticamente status aprovado já registrado. |

### Bases e fontes de descoberta

1. **PubMed/MEDLINE:** literatura biomédica; combinar vocabulário MeSH e termos livres (`[Mesh]`, `[tiab]`). Registrar consulta, data, filtros e identificador PMID/DOI.
2. **SciELO:** artigos e documentos disponíveis na coleção; registrar coleção/país, idioma, URL e DOI. Para páginas de sociedades hospedadas em SciELO, distinguir a plataforma da entidade autora.
3. **Portais oficiais do Ministério da Saúde:** normas, guias e protocolos brasileiros. Pesquisar no portal oficial/BVS quando for o canal de acesso, registrando entidade publicadora, edição, URL e situação normativa.
4. **BVS/LILACS, como complemento condicionado:** útil para literatura regional e português/espanhol. Guardar interface, base(s) selecionada(s), estratégia completa e data. Verificar RN16 antes de usar como rota aprovada.
5. **Sites institucionais de sociedades, como complemento:** pesquisar páginas oficiais de ABESO, SBME, SBAN e SVB para diretrizes/posicionamentos. Não presumir independência de conflito de interesse, revisão por pares, vigência ou licença. Registrar financiamento, patrocínio e declarações de conflito disponíveis; ausência de declaração é “não informado”, não “sem conflito”.

Fontes localizadas por busca reversa/citações podem ser acrescentadas ao registro, marcadas como busca suplementar, com método e data próprios. Não misturar seus resultados às contagens de uma base sem distingui-las.

## Estratégia de busca

Definir antes da consulta: (a) pergunta/tema e população; (b) conceito principal e sinônimos; (c) desfechos relevantes; (d) base/interface; (e) filtros; (f) data e responsável. Traduzir conceitos em DeCS para português/espanhol e MeSH para inglês quando disponíveis, mas combinar descritores com texto livre para cobrir indexação incompleta. Salvar a string realmente executada, não apenas uma estratégia planejada. A janela padrão é móvel: data de execução menos 10 anos até a data de execução, inclusive. Usar datas completas quando a plataforma permitir; se só aceitar ano, declarar que o limite é aproximado e avaliar à parte os registros do ano de corte. No PubMed, a busca pode usar `YYYY/MM/DD:YYYY/MM/DD[dp]`; o filtro relativo de dez anos é uma alternativa, mas registrar a data exata de execução porque a janela muda. O PubMed informa que filtros por data de publicação abrangem datas impressas e eletrônicas e que os filtros por tipo podem deixar de recuperar registros ainda não indexados.

Operadores: `OR` reúne sinônimos; `AND` cruza conceitos; aspas buscam expressão; parênteses tornam a lógica explícita; truncamento e campos são específicos de cada plataforma. Adaptar e registrar sintaxe por base. Não combinar tantos conceitos que a busca omita diretrizes relevantes; fazer busca sensível principal e consulta focada suplementar quando necessário.

### Blocos reutilizáveis

Estes blocos são ponto de partida, não strings universais. Confirmar cada descritor no DeCS/MeSH e registrar a tradução executada.

| Tema | Descritores e termos livres iniciais |
|---|---|
| Hipertensão / DASH | DeCS/MeSH `Hypertension`, `Diet, Sodium-Restricted`, `Diet, Healthy`; texto `hipertensão`, `pressão arterial`, `DASH`, `Dietary Approaches to Stop Hypertension` |
| Glicemia / pré-diabetes | DeCS/MeSH `Prediabetic State`, `Blood Glucose`, `Glycemic Control`; texto `pré-diabetes`, `glicemia`, `glicemia de jejum`, `prediabetes`, `blood glucose` |
| Bioativos alimentares | DeCS/MeSH `Phytochemicals`, `Bioactive Compounds`, mais compostos nomeados pela pergunta; texto `compostos bioativos`, `sulforafano/sulforaphane`, `curcumina/curcumin`, `piperina/piperine`, etc. Evitar tratar compostos distintos como uma intervenção única. |
| Doença renal e potássio | DeCS/MeSH `Chronic Kidney Disease`, `Potassium`, `Diet`; texto `doença renal crônica`, `chronic kidney disease`, `potássio`, `potassium`, em combinação com hipertensão/DASH quando a pergunta exigir |

Para cada tema, salvar a consulta de descritores e a consulta de termos livres ou sua combinação final. Vocabulários, nomes e disponibilidade podem mudar; anotar versão/data da consulta DeCS/MeSH.

## Critérios de seleção

### Inclusão para avaliação integral

- Fonte identificável e verificável, com autoria institucional/pessoal, título, edição/versão e URL/DOI ou origem recebida claramente descrita.
- Relação direta com Nutrição e com uma pergunta educativa pertinente à população adulta do CULTIVA, ou norma necessária para delimitar o conteúdo.
- Desenho/tipo compatível com a pergunta; diretriz/norma vigente ou evidência científica cuja população, intervenção/exposição e desfechos sejam aplicáveis e explícitos.
- Registro bibliográfico não duplicado; quando houver versões, identificar a vigente e manter a relação entre substituída e substituta.

### Exclusão ou retenção pendente

- Fora do escopo educativo de Nutrição, população sem aplicabilidade justificável, ou conteúdo que exija resposta prescritiva individual (por exemplo, quantidade personalizada de carboidrato): não incorporar para tornar essa resposta permitida.
- Norma revogada/substituída sem valor histórico explícito; estudo incompatível com a pergunta; duplicata; resumo sem texto integral; texto ilegível ou sem revisão suficiente; origem/versão não verificável.
- Conflito de interesse material sem transparência/mitigação suficiente para uso pretendido: excluir ou manter pendente com motivo. Patrocínio não implica exclusão automática, mas exige avaliação explícita.
- Licença desconhecida, incompatível ou sem evidência para a utilização pretendida: manter pendente; não copiar para derivados técnicos até resolver a condição aplicável.
- Fonte de sociedade sem método, escopo claro ou declarações acessíveis pode permanecer candidata, mas não recebe aprovação automática por prestígio institucional.

Cada exclusão recebe uma razão primária padronizada no registro (fora do escopo; população; desenho/desfecho; versão/vigência; duplicata; sem texto integral; procedência; COI; licença; qualidade/conversão; outro, com explicação). “Pendente” não significa rejeitada; “não encontrado” não significa inexistente.

### Hierarquia de evidência e qualidade

Aplicar a hierarquia conforme pergunta e finalidade:

1. Norma/diretriz oficial vigente para obrigações e recomendações institucionais; avaliar autoridade, método e conflitos separadamente.
2. Diretriz clínica baseada em evidência; checklist do corpus e AGREE II complementar, se houver avaliadores disponíveis.
3. Revisão sistemática/metanálise diretamente pertinente; registrar protocolo, busca, risco de viés, heterogeneidade, população e certeza reportada.
4. Estudos primários adequados ao desfecho (ensaios, coortes, estudos diagnósticos etc.); não generalizar desenho ou associação além do que mediu.
5. Revisões narrativas e material educativo: contexto e rastreamento de referências, não substitutos automáticos de síntese sistemática.

GRADE pode aparecer no próprio documento para cada desfecho. Registrar categoria e justificativa reportadas, quando disponíveis. Não derivar um “nível GRADE da fonte” somando resultados de desfechos diferentes. Para discordâncias entre fontes, preservar a divergência e encaminhar revisão humana; não selecionar apenas a recomendação mais conveniente.

## Registro e fluxo

Usar o modelo [`nutricao/relatorios/buscas/modelo-registro.md`](nutricao/relatorios/buscas/modelo-registro.md). Registrar por fonte: data, base e interface, string exata, campos/limites, número recuperado, exportação/arquivo, deduplicados, triados, texto integral obtido, incluídos e excluídos por razão. O fluxograma segue campos inspirados em PRISMA e a documentação de busca em PRISMA-S; isso não torna a atividade uma revisão sistemática nem declara conformidade formal com esses padrões.

Triagem inicial pode ser assistida por automação/IA, mas a decisão de inclusão, conflito, licença, aprovação e uso técnico requer revisão humana registrada. Para texto integral, conferir conteúdo e conversão contra o original, inclusive tabelas, unidades e referências, seguindo o procedimento existente em `README.md`. Só uma decisão formal atualiza status no manifesto.

## Parâmetros e métricas recomendados

Separar **filtros de recuperação**, **critérios de elegibilidade**, **qualidade da evidência** e **qualidade da ingestão**. Não somar tudo em uma nota única: licença e escopo são condições de elegibilidade, enquanto risco de viés e relevância são dimensões distintas. Na primeira rodada, registrar valores sem impor cortes numéricos não validados.

| Dimensão | Parâmetro/métrica | Como registrar e usar |
|---|---|---|
| Recuperação | Janela de publicação (10 anos), idioma, base/interface, população/idade, tipo de publicação | Guardar filtro exato e sua justificativa. Data é o único corte temporal padrão; evitar filtros de tipo/idade se houver risco de perder registros não indexados. |
| Pergunta | População 18+, condição/exposição/intervenção, comparador quando pertinente, desfecho e contexto | Definir a pergunta antes da busca (PICO ou estrutura adequada ao tipo de pergunta); na triagem, marcar aderência direta, parcial ou indireta e justificar. |
| Aplicabilidade | Adultos, população mista, país/contexto, cenário e correspondência com o caso educativo | Categorias explícitas; evidência pediátrica ou de cenário distante não é extrapolada automaticamente. |
| Desenho e rigor | Tipo de documento/desenho; método e limitações; risco de viés reportado; certeza GRADE reportada por desfecho | Usar a hierarquia do protocolo como prioridade. Não tratar desenho isolado como garantia de qualidade nem reavaliar GRADE sem método/equipe. |
| Diretrizes | Situação de vigência, método de elaboração, conflitos, AGREE II quando viável | Registrar versão/data e cada domínio. Dois avaliadores são preferíveis; sem segundo avaliador, marcar avaliação como preliminar. Sem nota de corte inventada. |
| Transparência e elegibilidade | Origem, autoria, versão, texto integral, conflito de interesse, licença e compatibilidade de uso | Campos obrigatórios de decisão; desconhecido = pendente. Fonte sem licença compatível não entra na ingestão técnica mesmo que seja relevante. |
| Fluxo da busca | Recuperados, duplicados, únicos, título/resumo triados, texto integral obtido, excluídos por motivo, candidatos e aprovados | Medir taxa de duplicidade, rendimento de triagem (candidatos pertinentes/triados) e taxa de obtenção de texto integral. São indicadores de eficiência do processo, não qualidade científica. |
| Conversão/ingestão | Páginas conferidas, cobertura de texto, tabelas/unidades preservadas, citações rastreáveis ao original, erros pendentes | Registrar por documento e amostra/páginas. Qualquer erro que altere resultado, unidade, recomendação ou citação bloqueia uso até correção. |
| Cobertura | Casos do golden set apoiados por fonte elegível, lacunas restantes e casos que devem continuar fora de escopo | Matriz caso → afirmação necessária → fonte/trecho aprovado. Medir cobertura sem transformar todo caso de benchmark em obrigação de ingestão. |

**Conjunto mínimo recomendado para cada candidato:** relevância direta à pergunta; população/contexto; desenho e limitações; vigência (para norma/diretriz); conflitos; licença; integridade do texto/conversão; vínculo a um caso ou lacuna documentada. Rastreabilidade, escopo e licença são gates, não pontos compensáveis. Contagem de citações, fator de impacto ou prestígio do publicador podem ajudar a priorizar leitura, mas não devem decidir inclusão: tendem a favorecer áreas, periódicos e documentos mais antigos e não substituem avaliação de método.

Após algumas buscas registradas, comparar rendimento e divergências entre revisores e então propor limites quantitativos com justificativa. Preservar também resultado zero, motivos de exclusão, textos não obtidos e pioras; não ajustar a métrica para fazer o protocolo parecer eficaz.

## Aplicação piloto: DASH e hipertensão em adultos

O registro [`2026-11-12-pubmed-dash-hipertensao.md`](nutricao/relatorios/buscas/2026-11-12-pubmed-dash-hipertensao.md) documenta a busca real PubMed e a triagem preliminar. Após a delimitação, a consulta foi refeita com janela móvel exata: 12 registros focados, 6 excluídos na triagem por título/resumo e 6 encaminhados para texto integral. A execução anterior por anos-calendário foi preservada como histórico e o PMID 26773016 foi removido por ser anterior a 12/11/2016. Até revisão integral, licença, conflitos e decisão formal, **incluídos no corpus = 0**. O piloto não alterou o manifesto nem adicionou documentos.

## Lacunas prioritárias ligadas às avaliações

As prioridades abaixo são propostas de busca, não prova de ausência total. Os casos citados são benchmarks versionados, não registros de conversas reais de usuários.

| Prioridade proposta | Tema e evidência local observada | Casos ligados | Próximo passo de busca |
|---|---|---|---|
| Alta | Hipertensão/DASH com comorbidade renal e potássio. ABESO 2022 já traz conteúdo DASH, então a lacuna é cobertura atual, norma específica e ressalvas para DRC/potássio, não ausência total. | v2 `V2-GRA-03`; v1 `Q08_MULTIHOP_GAP`, `Q16_NATURAL_GRAPH` | Buscar diretriz oficial vigente e sínteses sobre hipertensão + DRC, distinguindo recomendação de DASH, ingestão de potássio e exceções por condição clínica. O piloto PubMed é primeiro passo; localizar texto integral dos 7 candidatos e avaliar a diretriz brasileira identificada no relatório suplementar. |
| Média, condicionada | Glicemia/pré-diabetes: o pedido de gramas/dieta individualizada não deve ser “resolvido” por ingestão de fontes; materiais só podem apoiar educação geral, conforme guardrails. | v2 `V2-PRE-02`; v1 `Q09_LEGAL_TRAP` | Definir pergunta educativa não prescritiva antes de nova busca; consultar diretrizes oficiais de prevenção e educação em diabetes. |
| Média, escopo a confirmar | Compostos bioativos. ABESO inclui resveratrol; busca lexical local não encontrou sulforafano, curcumina e piperina. Não há caso v2 específico identificado; v1 traz exemplos exploratórios. | v1 `Q07_MULTIHOP_GAP`, `Q13_NATURAL_GRAPH`; nenhum caso v2 específico localizado | Especificar quais afirmações educativas são desejadas e distinguir segurança/alegação terapêutica. Buscar cada composto e desfecho separadamente; não ampliar corpus por mera presença no benchmark. |
| Sem prioridade de ingestão | Kombucha, colágeno, hibisco e tire/car aparecem como casos fora de escopo no v2. | v2 `V2-FOR-01` a `V2-FOR-04` | Preservar comportamento de abstenção/limite de escopo. Não buscar fontes com objetivo de responder conteúdo explicitamente fora de escopo. |

Prioridades devem ser revistas após resultados do benchmark offline e avaliação de cobertura. Uma lacuna do benchmark não é, por si, requisito aprovado nem evidência de necessidade clínica.

## Pendências explícitas

- Confirmar o texto oficial do RN16 e se BVS/LILACS e páginas de sociedades estão autorizadas como fontes/rotas de descoberta. Links à documentação original estão listados em [`../docs/contexto-projeto.md`](../docs/contexto-projeto.md); a consulta desta branch não confirmou o conteúdo original completo.
- Decidir aprovação formal do protocolo, dos filtros padrão, da auditoria retroativa e do uso complementar de AGREE II/GRADE.
- Identificar segundo avaliador para eventual AGREE II e estabelecer, se desejado, regra de decisão/notas antes de avaliar diretrizes.
- Reexecutar e registrar o piloto com a janela móvel exata de 10 anos; a busca registrada usou anos-calendário e inclui ao menos um registro de janeiro de 2016, fora da nova janela em 12/11/2026.
- Concluir leitura integral, análise de COI/licença, qualidade da transcrição e decisão dos candidatos após a busca corrigida. Busca ou triagem preliminar não autoriza inclusão.

## Referências metodológicas

- [PRISMA 2020](https://www.prisma-statement.org/) e [PRISMA-S: extensão para relato de buscas](https://www.prisma-statement.org/prisma-search): referência para campos de identificação, seleção e documentação das estratégias. Este protocolo toma os campos como inspiração operacional; não declara revisão sistemática nem conformidade formal.
- [AGREE II: manual e instrumento](https://www.agreetrust.org/wp-content/uploads/2017/12/AGREE-II-Users-Manual-and-23-item-Instrument-2009-Update-2017.pdf): instrumento de avaliação de diretrizes clínicas; registrar versão e avaliadores.
- [GRADE Working Group](https://www.gradeworkinggroup.org/): método de avaliação da certeza da evidência e força de recomendação, aplicado por desfecho.
- [MeSH Browser](https://meshb.nlm.nih.gov/): vocabulário controlado da National Library of Medicine; confirmar descritores e termos de entrada na data de cada busca.
- [Ajuda do PubMed — filtros por data e tipos de publicação](https://pubmed.ncbi.nlm.nih.gov/help/): sintaxe da janela de publicação, datas eletrônicas/impressas e limitações de indexação dos filtros.
- [Manual LILACS/BVS](https://docs.bvsalud.org/biblioref/2024/11/883168/lilacs-2-manualdescricao-en.pdf): referência sobre LILACS como base cooperativa no ecossistema BVS. Não substitui a confirmação de autorização no RN16.
