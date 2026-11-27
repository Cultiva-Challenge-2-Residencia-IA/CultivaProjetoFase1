# ADR 0005: Arquitetura multiagentes com Chat geral, Chats de área e Histórico

* **Status:** Proposta técnica; aprovação formal da equipe pendente
* **Data:** 2026-11-24; revisado em 2026-11-25 (Projetor de contexto e Fatos do Usuário, implementados na issue #112; medição em `eval/projetor/`)
* **Escopo:** `src/chat/`, `src/orquestrador/` (roteamento, reescrita, Projetor de contexto e Sincronizador), `src/agents/fisica/`, `src/guardrails/alerta/`, corpus de Saúde Física e endpoints `/chat/*` da API (com a autenticação da issue #108)
* **Evidência:** issue #99; critérios e resultados em `eval/multiagentes/`. A revisão de 25/11 vem de uma entrevista de desenho com o mantenedor, a partir do RN06 e do RF-IA09
* **Vocabulário:** `GLOSSARY.md` (Orquestrador, Agente de área, Sincronizador, Chat geral, Chat de área, Portão, Sinal de alerta, Subpergunta, Projetor de contexto, Fato do Usuário)

## Contexto

A entrega pede um sistema multiagentes. Até a issue #99, o grafo do LangGraph (#76) tinha um só agente, o de Nutrição, e cada pergunta era respondida sem histórico. Os requisitos separam dois papéis: cada agente responde só na sua área e redireciona as perguntas de outra (RF-IA06), e um agente sincronizador integra as áreas compartilhando só o contexto necessário (RF-IA09).

O diferencial do produto é centralizar as áreas da vida do Usuário: os registros alimentam uma base única, e um agente usa o que foi reportado em outra área para responder melhor (RN06, com o exemplo do Agente de Estudos que usa o cansaço reportado em Saúde; premissas e visão do produto no Documentacao-Cultiva). O critério do RF-IA09 é que nenhum agente receba dados de abas **desnecessárias**, e não que cada agente fique isolado na própria área. A primeira versão deste ADR (24/11) isolava cada Agente de área no Histórico da própria área; essa leitura foi substituída em 25/11 pelo Projetor de contexto.

## Decisão

* **Peças:**
  * **Orquestrador:** aplica os Portões e decide a área ou as áreas de cada mensagem; não responde conteúdo.
  * **Agentes de área:** Nutrição e Saúde Física, cada um com o seu corpus aprovado, o seu guardrail legal (Lei 8.234/1991 e Lei 9.696/1998) e o mesmo subgrafo (busca híbrida, "não sei", síntese com citação por frase, guardrail de saída).
  * **Projetor de contexto** (decidido e implementado em 25/11, issue #112): antes de cada Agente de área, nos três chats, escolhe os Fatos do Usuário relacionados à Subpergunta, de qualquer área, e entrega só esses ao agente. É uma peça própria do Orquestrador, separada do Sincronizador.
  * **Sincronizador:** quando a mensagem envolve as duas áreas, o LLM cruza as frases já citadas dos dois agentes numa resposta única, conferida pela mesma checagem de citação por frase; se a checagem reprovar, se alguma frase vier sem citação literal ou se não houver LLM, as respostas ficam lado a lado.
* **Chats:** Chat geral (Orquestrador e Sincronizador) e um Chat de área por agente. O Chat orquestra em Python (`src/chat/servico.py`) e chama os subgrafos LangGraph de cada Agente de área; o grafo principal do LangGraph (`construir_grafo`) continua servindo o `/consult`, os benchmarks e a demonstração da semana 2, só com Nutrição. Num Chat de área, o agente responde só a parte da sua área e indica o chat certo para o resto.
* **Portões, iguais nos três chats:** risco (RF-IA03), **sinal de alerta** (novo: dor no peito, desmaio, falta de ar intensa, lesão aguda; mensagem fixa para parar e procurar atendimento) e prompt injection.
* **Roteamento:** as regras de vocabulário decidem sempre que alguma área tem termo (uma ou as duas). Sem termo, decide o LLM (uma área, as duas ou fora das áreas). Sem termo e sem LLM, o Agente de Nutrição, que dá o "não sei" fora do domínio, como antes. Fora das áreas (e Estudos, que ainda não tem agente) recebe mensagem fixa.
* **Reescrita de consulta:** uma chamada ao LLM devolve a pergunta completa (pergunta de continuação resolvida com o Histórico), as Subperguntas por área (decomposição) e um trecho hipotético por Subpergunta (HyDE), no idioma das fontes da área. A busca roda com a pergunta e com esses textos, e as listas são fundidas por RRF. Ligada por padrão só se a medição não piorar a busca (`CULTIVA_REESCRITA_LLM`, ver Evidência).
* **Histórico:**
  * SQLite local (`data/conversas.sqlite3`, ignorado pelo Git), uma linha por mensagem, com o chat e as áreas que responderam;
  * o Chat geral lê o Histórico dos Chats de área do mesmo Usuário; os Chats de área não leem o geral;
  * cada Agente de área recebe o Histórico recente da área dele, para a continuidade da conversa, como contexto no prompt, nunca como fonte; o que a pessoa disse em outras áreas chega pelos Fatos do Usuário, não pelas mensagens;
  * janela por orçamento de tokens (implementado em 25/11: `CULTIVA_HISTORICO_TOKENS`, proposta de 2.500, e no máximo `CULTIVA_JANELA_HISTORICO` mensagens, 20), no lugar das 6 mensagens de antes: as perguntas do Usuário entram inteiras e as respostas do assistente encurtadas (primeiras frases, sem citações); o que é antigo fica com os Fatos do Usuário;
  * texto sem máscara no SQLite (é a conversa do Usuário); máscara de dados pessoais no que vai ao LLM e ao Langfuse; mensagem de risco guardada só com as categorias, e mensagem de sinal de alerta só com os nomes dos sinais;
  * guardado até o Usuário apagar (`DELETE /chat/usuarios/{id}` e `.../conversas/{id}`).
* **Fatos do Usuário (decidido e implementado em 25/11, issue #112; `src/orquestrador/fatos.py`, `src/chat/fatos.py`):**
  * **esquema fixo de categorias**, com a área definida pelo assunto e não pelo chat: Saúde Física (atividade praticada, frequência ou volume, objetivo de treino, limitação física declarada), Nutrição (padrão alimentar, jejum e horários, restrição ou alergia, objetivo alimentar) e condição de saúde declarada;
  * **extração em segundo plano:** o LLM local extrai os fatos só das mensagens do Usuário, depois que a resposta é enviada, e grava numa tabela própria; nada que acionou o Portão de risco ou o de sinal de alerta vira fato;
  * **validade temporal:** um fato novo da mesma categoria encerra a validade do anterior, que fica guardado com a data de fim (RNF08); fato sem atualização expira em 90 dias (proposta);
  * **seleção:** a escolha dos fatos relevantes para cada Subpergunta entra na mesma chamada JSON da reescrita; sem LLM, nenhum fato é passado (falha fechada), e cada fato entregue a um agente fica registrado (critério do RF-IA09);
  * **uso:** o fato só personaliza e relaciona a resposta, nunca é fonte; a frase que o usa leva o marcador `[CONTEXTO]`, aceito pela checagem de citação só quando o fato foi entregue, e afirmação de saúde continua exigindo `[T#]`; nada é prescrito a partir dele;
  * **condição de saúde:** só direciona a busca para evidência da população certa e reforça a indicação de profissional; nunca ajusta quantidade, meta, dose ou plano (RN01 a RN03, Leis 8.234 e 9.696);
  * **consentimento:** a memória fica desligada até o Usuário aceitar, com aceite separado para condição de saúde (dado sensível, LGPD art. 11), revogável; sem App, o aceite vem de `PUT /chat/usuarios/{id}/memoria`, e `CULTIVA_MEMORIA_PADRAO` (`desligada`, `ligada` ou `ligada_com_saude`) vale só para testes e uso local com dados sintéticos;
  * **observabilidade:** o texto dos fatos não vai ao Langfuse; a máscara troca o texto pela categoria, e o trace leva só a contagem e as categorias entregues;
  * **controle:** a resposta informa os fatos usados (`fatos_usados`); `GET /chat/usuarios/{id}/fatos` lista e `DELETE .../fatos/{fato_id}` apaga; apagar uma Conversa ou um Usuário apaga os fatos derivados. A pessoa vê os fatos guardados mesmo depois de revogar o consentimento, para poder apagá-los.
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
* **Cada Agente de área isolado no Histórico da própria área** (primeira versão deste ADR, 24/11): protegia contra vazamento, mas impedia o cruzamento entre áreas que é o diferencial do produto (RN06) e lia o RF-IA09 de forma mais restrita do que o critério de aceite pede.
* **Mensagens brutas de outras áreas no prompt:** mais simples, mas leva ruído e dado que a pergunta não pede, e não dá para provar no log o que foi compartilhado.
* **Fatos livres com busca por similaridade** (padrão do Mem0 e da memória do ChatGPT): captura qualquer fato, mas a relevância fica no cosseno e é difícil de auditar; o esquema fixo (padrão de perfil do LangMem) é previsível e testável.
* **Extração durante a resposta** (*hot path*): o fato valeria na mesma mensagem, mas cada resposta ganharia uma chamada ao LLM.
* **Escolha do contexto dentro do Sincronizador:** seguiria a letra do RF-IA09, mas misturaria duas funções numa peça.
* **Substituir o fato anterior** (padrão do Mem0): mais simples, perde o histórico do fato; a validade temporal (padrão do Zep) mantém a rastreabilidade.

## Consequências e limitações

* **Autenticação provisória (issue #108):** o token confere quem é o Usuário, mas ainda não há App nem provedor de identidade que o emita; o segredo é compartilhado entre o App e a API (HMAC), sem rotação, sem revogação antes da expiração e sem escopo por endpoint. Até lá, uso local e dados sintéticos. A troca por um provedor de identidade (JWT assinado com chave assimétrica, por exemplo) muda só `src/chat/autenticacao.py`. O `POST /feedback/incorrect` continua sem autenticação (quem sabe um `response_id` pode marcá-lo como incorreto). A resposta 403 a um `conversa_id` de outro Usuário revela que o id existe: o App deve gerar ids aleatórios (UUID).
* As regras de roteamento são por vocabulário: paráfrases sem termo de área dependem do LLM.
* A reescrita e o Sincronizador acrescentam chamadas ao LLM local: latência maior no Chat geral. Na medição da issue #107 (`eval/multiagentes/resultados.md`, numa RX 9060 XT de 16 GB), depois de igualar o `num_ctx` de todas as chamadas e de rodar os Agentes em paralelo (com `OLLAMA_NUM_PARALLEL=2` no Ollama), o p95 do Chat geral no `dev` ficou em cerca de 20 s para uma área e 34 s para duas.
* O Histórico em texto puro é tratamento de dado pessoal de saúde; o RIPD do repositório (`docs/ripd/`) descreve retenção, exclusão e acesso, mas a versão oficial do RIPD, se houver, fica no repositório Documentacao-Cultiva e precisa ser conferida.
* O corpus de Saúde Física está quase todo em inglês; as respostas saem em português, e as citações literais ficam no idioma da fonte.
* Em 26/11/2026, 11 artigos de treino de força e recuperação (issue #115) também foram aprovados pelo mantenedor, e o corpus de Saúde Física passou a 29 fontes aprovadas.
* As 18 fontes de Saúde Física (17 do corpus e o ACSM 2026) foram aprovadas pelo mantenedor (feliperodri0) em 24/11/2026, depois da conferência dos derivados contra os originais. Licença restritiva ou `pendente` não bloqueia o uso, pelo aceite de risco de 06/11/2026.
* Os casos de avaliação têm o mesmo autor do código.
* **Fatos do Usuário são tratamento novo de dado pessoal de saúde**, inclusive dado sensível (condição de saúde): precisam entrar no RIPD e na arquitetura do Documentacao-Cultiva antes de qualquer uso com pessoas reais. A extração pelo LLM pode errar; por isso o fato só personaliza, a resposta mostra o que foi usado e a pessoa pode apagar.
* **Critérios da implementação**, escritos antes de medir, com conversas de avaliação `dev` e `test`: o fato relacionado é usado, o não relacionado não é passado, condição de saúde nunca altera quantidade, a fidelidade das citações não piora e a latência fica dentro de um limite.

## Revisão

Revisar quando houver a interface do App (os registros estruturados viram a fonte preferida dos Fatos do Usuário, por serem confirmados pelo Usuário, RF-A10) ou o Agente de Estudos, depois da medição do Projetor de contexto, ou se a medição da reescrita ou do roteamento mudar com outro modelo.
