# Orientações para trabalhar no CULTIVA

- Leia `README.md`, `docs/contexto-projeto.md` e `corpus/manifest.yaml` antes de alterar o projeto. Consulte os documentos originais vinculados no contexto para regras e requisitos; informe limitações de acesso sem presumir conteúdo.
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

- O corpus de Nutrição e o RAG que o consome estão implementados (21 de 22 fontes aprovadas). O trabalho atual é melhorar a recuperação e a avaliação do RAG de Nutrição (issues #13, #15 e #28). Outras abas e a infraestrutura de produção dependem de solicitação própria. O portão de risco (#9) existe para texto; mudanças no léxico ou na mensagem de acolhimento precisam ser revisadas no PR e medidas em `eval/risco/casos.json`.
- Adote a convenção descrita em `docs/contexto-projeto.md`: originais em `corpus/nutricao/originais/` e versões Markdown revisadas em `corpus/nutricao/markdown/`. Preserve os originais e a correspondência por identificador e versão.
- Mantenha `corpus/manifest.yaml` como catálogo único das fontes, com a estrutura existente `version` e `sources`. Reutilize `id`, `source`, `license` e `version`; registre também `approval_status` e os caminhos dos arquivos conforme o contexto. Não crie um catálogo paralelo `sources.yaml`.
- Toda fonte precisa manter origem verificável, licença, versão e status de revisão. Metadados ausentes ficam explicitamente pendentes; não suponha licença nem cadastre fontes fictícias.
- A conversão para Markdown não aprova uma fonte. Confira texto, tabelas, unidades e referências contra o original; uso técnico exige revisão concluída, fonte aprovada e licença compatível com o uso pretendido (RN04, RN16, RN17, RF-IA01).
- Licenças: a equipe registrou em 06/11/2026 um aceite de risco para o uso acadêmico e sem fins lucrativos (ver `corpus/README.md`). Isso não autoriza supor licença: continue registrando a licença real ou `pendente`, e não estenda o aceite a uso comercial, vitrine paga (RN12) ou publicação do corpus sem nova decisão.
- Separe o corpus científico de dados pessoais: perfis, registros de hábitos/saúde, conversas, fotos, áudios e PDFs enviados por usuários não entram no corpus, no manifesto ou em seus derivados. O núcleo integrado de registros do produto não elimina essa separação.

## Verificação

- Em alterações documentais, confira links, caminhos, consistência com as fontes e o diff completo, incluindo arquivos novos; execute `git diff --check`.
- Ao alterar código, rode `uv run ruff check .` e `uv run pytest -q`. Ao alterar o corpus, rode `corpus/scripts/verify_corpus.py`. Quando a mudança puder afetar a recuperação ou as respostas, rode o benchmark offline e o `gate.py` (comandos no `CLAUDE.md`) e registre as métricas, inclusive as que pioraram.
- Ao concluir, informe arquivos alterados, verificações realizadas e pendências; mantenha decisões em aberto identificadas como tal.
