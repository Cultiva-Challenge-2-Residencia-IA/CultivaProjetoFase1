# Orientações para trabalhar no CULTIVA

> **Mantenha este arquivo e o `CLAUDE.md` atualizados.** Eles são a referência de agentes e pessoas sobre o estado do projeto. Quem muda comportamento, arquitetura, comandos, fluxo de trabalho ou uma decisão da equipe atualiza os dois **no mesmo PR**. Antes de concluir uma tarefa, confira se algo que eles afirmam ficou desatualizado (issues citadas, números, módulos, flags, decisões) e corrija. Informação velha aqui é pior do que nenhuma, porque leva a decisões erradas.

- Leia `README.md`, `CONTRIBUTING.md`, `corpus/README.md` e `corpus/manifest.yaml` antes de alterar o projeto. O `docs/contexto-projeto.md` (03/11/2026) tem o histórico, mas está desatualizado em relação ao corpus e ao código (veja "Inconsistência conhecida" no `CLAUDE.md`). Consulte os documentos originais vinculados no contexto para regras e requisitos; informe limitações de acesso sem presumir conteúdo.
- Inspecione `git status` e os arquivos envolvidos. Preserve alterações locais e limite o diff ao pedido; não reverta, mova nem sobrescreva trabalho existente sem necessidade autorizada.
- O CULTIVA é um projeto da Residência em Inteligência Artificial para jovens adultos e estudantes (18+), com Nutrição, Saúde Física e Estudos. A IA oferece apoio educativo e organizacional, sem diagnóstico, prescrição ou substituição de profissionais.
- Parte da árvore ainda é esqueleto: diretórios só com `.gitkeep` (como `src/agents/estudos/`, `src/agents/fisica/` e `src/broker/`) não são funcionalidades implementadas. O que existe de fato (pipeline de corpus, RAG de Nutrição, testes e CI) está descrito no `CLAUDE.md` e no `README.md`; não invente stack, comandos nem testes além deles.
- A arquitetura do repositório `Documentacao-Cultiva` é uma **proposta provisória, ainda não validada**. Diferencie requisitos, propostas, pendências e implementação observada.

## Análise crítica e evidências

- Classifique cada afirmação: **requisito aprovado** somente com referência explícita à decisão de aprovação; **requisito documentado, aprovação não confirmada** quando faltar essa evidência; **proposta técnica** para uma solução candidata; **hipótese** para benefício ou comportamento ainda a testar. Prioridade no MVP, presença na documentação e implementação não comprovam aprovação ou eficácia.
- Avalie criticamente a solução existente, inclusive decisões anteriores e estas orientações. Para inconsistências e alternativas, apresente evidência verificável (arquivo/trecho, documento ou resultado), separe observação de inferência e explique impactos, limitações e como comparar as opções.
- Não presuma que a arquitetura mais complexa é melhor. Compare propostas com alternativas mais simples sob os mesmos critérios e explicite os custos e benefícios ainda desconhecidos.
- As avaliações devem poder revelar falhas e resultados desfavoráveis ao projeto. Defina critérios antes da comparação, preserve resultados negativos, registre método, versões, casos e limitações; não selecione apenas exemplos favoráveis nem ajuste métricas para encobrir falhas. Admita revisão de decisões, simplificação ou abandono de uma proposta quando a evidência justificar.
- Ausência de implementação ou de testes significa falta de evidência de execução; não a apresente como sucesso nem como falha medida. Aprovação não confirmada também não significa rejeição.

## Etapa atual: corpus e RAG de Nutrição

- O corpus de Nutrição e o RAG que o consome estão implementados (21 de 22 fontes aprovadas), com portão de risco, defesa contra prompt injection, máscara de dados pessoais (#9) e "não sei" fora do domínio (#6). Outras abas e a infraestrutura de produção dependem de solicitação própria.
- Trabalho em aberto mais relevante: o detector de risco **não cumpre o RF-IA03** em frases novas (recall de 0,133 no holdout cego; camada semântica na #48), o guardrail de prescrição deixa passar pedidos parafraseados (#39), a verificação de citações e fundamentação (#12), a rastreabilidade por resposta (#11), a comparação de frameworks de guardrail para o "não sei" e a fundamentação (#52), e as decisões de corpus (#15, #28, #47).
- O portão de risco existe só para texto; mudanças no léxico ou na mensagem de acolhimento precisam ser revisadas no PR e medidas nos dois conjuntos de `eval/risco/`. O léxico e o holdout mudam em PRs de pessoas diferentes (`eval/risco/README.md`). Não amplie o léxico a partir do holdout.
- Layout do corpus: originais em `corpus/nutricao/originais/<nome>.pdf` (layout plano, com a versão no manifesto e no nome do arquivo), Markdown convertido em `corpus/nutricao/markdown/` e Trechos em `corpus/nutricao/rag/`. Preserve os originais e a correspondência por identificador e versão (`corpus/README.md`).
- Mantenha `corpus/manifest.yaml` como catálogo único das fontes, com a estrutura existente `version` e `sources`. Reutilize `id`, `source`, `license` e `version`; registre também `approval_status` e os caminhos dos arquivos conforme o contexto. Não crie um catálogo paralelo `sources.yaml`.
- Toda fonte precisa manter origem verificável, licença, versão e status de revisão. Metadados ausentes ficam explicitamente pendentes; não suponha licença nem cadastre fontes fictícias.
- A conversão para Markdown não aprova uma fonte. Confira texto, tabelas, unidades e referências contra o original; uso técnico exige revisão concluída e `approval_status: aprovado` (RN04, RN16, RN17, RF-IA01).
- Licenças: a equipe registrou em 06/11/2026 um aceite de risco para o uso acadêmico e sem fins lucrativos (ver `corpus/README.md`). Por isso a licença **não é critério de aprovação** nem bloqueia o uso técnico. Isso não autoriza supor licença: continue registrando a licença real ou `pendente`, e não estenda o aceite a uso comercial, vitrine paga (RN12) ou uso fora deste projeto sem nova decisão.
- Publicação do corpus (decisão de 12/11/2026): o repositório continua **público com os PDFs originais**, os Markdown e os Trechos, dentro do mesmo aceite de risco. Se um titular pedir, o arquivo e os derivados saem do repositório (`corpus/README.md`).
- Separe o corpus científico de dados pessoais: perfis, registros de hábitos/saúde, conversas, fotos, áudios e PDFs enviados por usuários não entram no corpus, no manifesto ou em seus derivados. O núcleo integrado de registros do produto não elimina essa separação.

## Provedor de LLM e dados pessoais (ADR 0003)

- O padrão é **Ollama local** (`LLM_PROVIDER=ollama`, com `OLLAMA_NO_CLOUD=1`). Sem Ollama disponível, o consultor usa a síntese extrativa local, que também é o modo do CI.
- A Groq é alternativa desativada por padrão: exige `LLM_PROVIDER=groq` **e** `ALLOW_EXTERNAL_LLM=true`, além da chave. Mesmo assim, só com entradas sintéticas ou desidentificadas, até que retenção, contrato de não treinamento e LGPD sejam verificados.
- A máscara de dados pessoais (`src/guardrails/pii`) é defesa adicional, não anonimização.

## Avaliação

- **Ajuste só no `dev`.** O split `test` dos conjuntos (`eval/golden/v2/`, `eval/abstencao/`) e os holdouts (`eval/risco/holdout.json`) medem; não orientam mudanças. Um holdout que orientou regras vai para o `dev`, e o próximo é escrito por outra pessoa, sem olhar as regras.
- Números medidos só no que orientou a solução indicam cobertura, não generalização; diga isso quando apresentá-los.
- Gate com falha conhecida (`falha_conhecida` em `eval/gates.toml`) continua sendo falha: ele só deixa de pintar o job de vermelho. Remova a marcação quando a issue citada resolver.

## Verificação

- Em alterações documentais, confira links, caminhos, consistência com as fontes e o diff completo, incluindo arquivos novos; execute `git diff --check`.
- Ao alterar código, rode `uv run ruff check .` e `uv run pytest -q`. Ao alterar o corpus, rode `corpus/scripts/verify_corpus.py`. Quando a mudança puder afetar a recuperação ou as respostas, rode o benchmark v1 duas vezes (os relatórios precisam ser idênticos), o benchmark v2 e o `gate.py` (comandos no `CLAUDE.md`), e registre as métricas, inclusive as que pioraram.
- Abra issues e PRs com os modelos de `.github/` e siga o fluxo do `CONTRIBUTING.md` (Conventional Commits em português, `Closes #N` ou `Refs #N`, revisão por outra pessoa).
- Ao concluir, confira se `AGENTS.md` e `CLAUDE.md` continuam corretos e atualize-os no mesmo PR quando a mudança os afetar.
- Ao concluir, informe arquivos alterados, verificações realizadas e pendências; mantenha decisões em aberto identificadas como tal.
