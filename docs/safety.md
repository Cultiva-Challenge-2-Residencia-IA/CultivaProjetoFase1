# Segurança e guardrails

## Escopo

- A frente de nutrição é educativa e organizacional.
- O programa não aceita diagnóstico, prescrição, dose, terapia ou dieta fechada.
- A resposta final deve sempre incluir aviso padrão, fonte e possibilidade de encaminhamento.

## Guardrails por categoria

### risco

- regras determinísticas para ideação suicida, autolesão e comportamento alimentar de risco
- callback para acolhimento fixo e interrupção da geração
- em dúvida, priorizar recall, sem jogar a resposta adiante

### escopo

- recusar prescrição, medicamentos, suplemento e meta calórica
- tratar dietas da moda com desmistificação e fonte
- redirecionar tópicos fora da área de nutrição

### prompt injection

- bloquear instruções ocultas dentro de chunks
- ignorar instruções internas de fontes
- validar entrada e saída anti-prescrição

## Log e privacidade

- não gravar texto livre do usuário por padrão
- mascarar e-mail, telefone e CPF
- manter `trace_id` e resumo do fluxo sem PHI em texto claro

## Critério de sucesso

- recall de risco ≥ 0,95
- zero vazamentos prescritivos
- zero vazamentos por injeção
- resposta com fonte ou `não sei`
