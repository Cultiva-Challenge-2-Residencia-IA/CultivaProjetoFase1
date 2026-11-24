# ADR 0005: Arquitetura multiagentes com Chat geral, Chats de área e Histórico

* **Status:** Proposta técnica; aprovação formal da equipe pendente
* **Data:** 2026-11-24
* **Escopo:** `src/chat/`, `src/orquestrador/` (roteamento, reescrita e Sincronizador), `src/agents/fisica/`, `src/guardrails/alerta/`, corpus de Saúde Física e endpoints `/chat/*` da API (com a autenticação da issue #108)
* **Evidência:** issue #99; critérios e resultados em `eval/multiagentes/`
* **Vocabulário:** `GLOSSARY.md` (Orquestrador, Agente de área, Sincronizador, Chat geral, Chat de área, Portão, Sinal de alerta, Subpergunta)

## Contexto

A entrega pede um sistema multiagentes. Até a issue #99, o grafo do LangGraph (#76) tinha um só agente, o de Nutrição, e cada pergunta era respondida sem histórico. Os requisitos separam dois papéis: cada agente responde só na sua área e redireciona as perguntas de outra (RF-IA06), e um agente sincronizador integra as áreas compartilhando só o contexto necessário (RF-IA09).

## Decisão

* **Peças:**
  * **Orquestrador:** aplica os Portões e decide a área ou as áreas de cada mensagem; não responde conteúdo.
  * **Agentes de área:** Nutrição e Saúde Física, cada um com o seu corpus aprovado, o seu guardrail legal (Lei 8.234/1991 e Lei 9.696/1998) e o mesmo subgrafo (busca híbrida, "não sei", síntese com citação por frase, guardrail de saída).
  * **Sincronizador:** quando a mensagem envolve as duas áreas, o LLM cruza as frases já citadas dos dois agentes numa resposta única, conferida pela mesma checagem de citação por frase; se a checagem reprovar, se alguma frase vier sem citação literal ou se não houver LLM, as respostas ficam lado a lado.
* **Chats:** Chat geral (Orquestrador e Sincronizador) e um Chat de área por agente. O Chat orquestra em Python (`src/chat/servico.py`) e chama os subgrafos LangGraph de cada Agente de área; o grafo principal do LangGraph (`construir_grafo`) continua servindo o `/consult`, os benchmarks e a demonstração da semana 2, só com Nutrição. Num Chat de área, o agente responde só a parte da sua área e indica o chat certo para o resto.
* **Portões, iguais nos três chats:** risco (RF-IA03), **sinal de alerta** (novo: dor no peito, desmaio, falta de ar intensa, lesão aguda; mensagem fixa para parar e procurar atendimento) e prompt injection.
* **Roteamento:** as regras de vocabulário decidem sempre que alguma área tem termo (uma ou as duas). Sem termo, decide o LLM (uma área, as duas ou fora das áreas). Sem termo e sem LLM, o Agente de Nutrição, que dá o "não sei" fora do domínio, como antes. Fora das áreas (e Estudos, que ainda não tem agente) recebe mensagem fixa.
* **Reescrita de consulta:** uma chamada ao LLM devolve a pergunta completa (pergunta de continuação resolvida com o Histórico), as Subperguntas por área (decomposição) e um trecho hipotético por Subpergunta (HyDE), no idioma das fontes da área. A busca roda com a pergunta e com esses textos, e as listas são fundidas por RRF. Ligada por padrão só se a medição não piorar a busca (`CULTIVA_REESCRITA_LLM`, ver Evidência).
* **Histórico:**
  * SQLite local (`data/conversas.sqlite3`, ignorado pelo Git), uma linha por mensagem, com o chat e as áreas que responderam;
  * o Chat geral lê o Histórico dos Chats de área do mesmo Usuário; os Chats de área não leem o geral;
  * cada Agente de área recebe só o Histórico da área dele (RF-IA09), como contexto no prompt, nunca como fonte;
  * até 6 mensagens por chat (`CULTIVA_JANELA_HISTORICO`);
  * texto sem máscara no SQLite (é a conversa do Usuário); máscara de dados pessoais no que vai ao LLM e ao Langfuse; mensagem de risco guardada só com as categorias, e mensagem de sinal de alerta só com os nomes dos sinais;
  * guardado até o Usuário apagar (`DELETE /chat/usuarios/{id}` e `.../conversas/{id}`).
* **Autenticação e posse da Conversa (issue #108):**
  * os endpoints `/chat/*` e de exclusão exigem `Authorization: Bearer <token>`; o token é assinado com HMAC-SHA256 (`src/chat/autenticacao.py`, formato `v1.<payload>.<assinatura>`, payload com `sub` e `exp`), com o segredo de `CULTIVA_AUTH_SEGREDO` (pelo menos 32 caracteres), e o App é quem o emitiria;
  * o Usuário vem do token; `usuario_id` no corpo ou na URL fica por compatibilidade e, se divergir do token, a chamada é recusada (403); sem token, token inválido ou expirado: 401;
  * sem segredo, os endpoints recusam (503); o modo sem autenticação, com o `usuario_id` do cliente, só existe com `CULTIVA_AUTH_DESLIGADA=true` e sem segredo, para uso local com dados sintéticos;
  * cada `conversa_id` pertence ao Usuário que o usou primeiro (tabela `conversas` do Histórico); outro Usuário com o mesmo id recebe 403, antes dos Portões e de qualquer gravação, e a exclusão só apaga Conversas do próprio Usuário. Ao apagar, o id fica livre de novo.
* **Langfuse:** cada Conversa é uma sessão; o id do Usuário vai com hash.
* **Feedback (RF-IA15):** cada resposta de Agente de área do `/chat/*` entra no registro de rastreabilidade com o seu `response_id`, como no `/consult`.

## Evidência

Critérios escritos antes da medição em `eval/multiagentes/criterios.md`; resultados em `eval/multiagentes/resultados.md`.

## Alternativas consideradas

* **Um único agente com prompt das duas áreas:** mais simples, mas mistura corpus e guardrails legais diferentes e contraria o RF-IA06.
* **LLM decide toda rota:** mais flexível, mas mais lento, não determinístico no CI e, na medição do `dev`, reduzia perguntas das duas áreas a uma só.
* **Sincronizador só lado a lado:** determinístico, mas não cruza as informações, que é o pedido do RF-IA09.
* **Checkpointer do LangGraph (`SqliteSaver`) para o Histórico:** guarda o estado por thread, mas o Chat geral precisa consultar os Chats de área do mesmo Usuário e filtrar por área; uma tabela própria faz isso direto.
* **Histórico compartilhado entre todos os chats:** mais contexto, mais dado pessoal circulando e risco de um agente responder fora da área.

## Consequências e limitações

* **Autenticação provisória (issue #108):** o token confere quem é o Usuário, mas ainda não há App nem provedor de identidade que o emita; o segredo é compartilhado entre o App e a API (HMAC), sem rotação, sem revogação antes da expiração e sem escopo por endpoint. Até lá, uso local e dados sintéticos. A troca por um provedor de identidade (JWT assinado com chave assimétrica, por exemplo) muda só `src/chat/autenticacao.py`. O `POST /feedback/incorrect` continua sem autenticação (quem sabe um `response_id` pode marcá-lo como incorreto). A resposta 403 a um `conversa_id` de outro Usuário revela que o id existe: o App deve gerar ids aleatórios (UUID).
* As regras de roteamento são por vocabulário: paráfrases sem termo de área dependem do LLM.
* A reescrita e o Sincronizador acrescentam chamadas ao LLM local: latência maior no Chat geral.
* O Histórico em texto puro é tratamento de dado pessoal de saúde; o RIPD do repositório (`docs/ripd/`) descreve retenção, exclusão e acesso, mas a versão oficial do RIPD, se houver, fica no repositório Documentacao-Cultiva e precisa ser conferida.
* O corpus de Saúde Física está quase todo em inglês; as respostas saem em português, e as citações literais ficam no idioma da fonte.
* As 18 fontes de Saúde Física (17 do corpus e o ACSM 2026) foram aprovadas pelo mantenedor (feliperodri0) em 24/11/2026, depois da conferência dos derivados contra os originais. Licença restritiva ou `pendente` não bloqueia o uso, pelo aceite de risco de 06/11/2026.
* Os casos de avaliação têm o mesmo autor do código.

## Revisão

Revisar quando houver a interface do App ou o Agente de Estudos, ou se a medição da reescrita ou do roteamento mudar com outro modelo.
