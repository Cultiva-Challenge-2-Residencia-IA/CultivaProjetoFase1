# CULTIVA: sistema multiagentes

Vocabulário das peças que conversam com o usuário e respondem a partir das fontes aprovadas, nas áreas de Nutrição e Saúde Física.

## Conversas

**Chat geral**:
Conversa que passa pelo Orquestrador e pode envolver mais de uma área.
_Evitar_: chat principal, orquestrador (como nome da conversa)

**Chat de área**:
Conversa presa a um único Agente de área, como o chat de Nutrição ou o de Saúde Física.
_Evitar_: chat específico, chat do agente

**Conversa**:
Sequência de mensagens de um Usuário num mesmo chat, identificada por um id e com contexto entre as mensagens.
_Evitar_: sessão, thread (fora do código)

**Usuário**:
Pessoa que conversa com o CULTIVA, identificada por um id; liga as Conversas dela nos diferentes chats.
_Evitar_: cliente, conta, paciente

**Histórico**:
Mensagens anteriores de uma Conversa. O Chat geral também lê o Histórico dos Chats de área do mesmo Usuário; os Chats de área não leem o do Chat geral.
_Evitar_: memória, contexto (quando se refere às mensagens guardadas)

## Agentes

**Orquestrador**:
Peça que recebe toda mensagem do Chat geral, aplica os portões e decide para qual Agente de área ou áreas ela vai. Não responde conteúdo.
_Evitar_: roteador (como nome da peça), chat geral

**Agente de área**:
Agente que responde só na sua área (Nutrição ou Saúde Física), a partir das fontes aprovadas dela, e redireciona perguntas de outra área.
_Evitar_: especialista, consultor

**Sincronizador**:
Peça que cruza as respostas de mais de um Agente de área numa resposta única, sem acrescentar fato que os agentes não trouxeram.
_Evitar_: integrador, agregador, orquestrador

**Portão**:
Verificação feita antes de qualquer Agente de área que pode encerrar a mensagem com uma resposta fixa (risco, prompt injection).
_Evitar_: filtro, guardrail (quando for o portão)

**Sinal de alerta**:
Sintoma físico que pede atendimento, e não resposta (dor no peito, desmaio, falta de ar anormal, lesão aguda); encerra a mensagem num Portão, em qualquer chat.
_Evitar_: risco (reservado para sofrimento psíquico e comportamento alimentar de risco, RF-IA03)

**Subpergunta**:
Parte de uma mensagem que cabe numa única área; uma mensagem que envolve as duas áreas vira uma Subpergunta para cada Agente de área.
_Evitar_: consulta, query

**Fora das áreas**:
Mensagem que não pertence a nenhuma área com agente; recebe o "não sei" fixo.
_Evitar_: fora do escopo, fora do domínio (quando se refere ao Chat geral)
