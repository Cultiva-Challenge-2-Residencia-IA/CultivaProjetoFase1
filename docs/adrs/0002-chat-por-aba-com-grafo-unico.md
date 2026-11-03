# Chat por Aba, com um único grafo

O usuário conversa dentro de cada Aba (Nutrição, Saúde Física, Estudos), sem um chat geral livre, mas todas as Abas passam pelo mesmo grafo (Portão de risco, guardrails, roteador, Context Broker, agente da Aba). Escolhemos isso porque cada agente responde só na sua área (RF-IA06), o que mantém o contexto mínimo, simplifica guardrails e RAG por Aba e permite avaliar cada Aba separadamente; o grafo único garante que a segurança é a mesma em qualquer chat.

## Consequences

- Pergunta de outra Aba não é respondida: recebe uma mensagem padrão sugerindo a Aba certa, sem repassar o texto a outro agente.
- Pergunta que cruza Abas (ex.: "estudo ou treino hoje?") vai para o "Meu dia", onde o agente sincronizador concilia as Abas.
- Um chat geral pode ser adicionado depois como mudança de interface, reaproveitando o mesmo roteador.
