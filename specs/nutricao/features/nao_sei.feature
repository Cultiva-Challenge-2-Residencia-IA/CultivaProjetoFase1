# language: pt

Funcionalidade: resposta sem evidência
  Cenário: sem suporte suficiente, retorna não sei
    Dado que a pergunta não tem resposta razoável no corpus
    Quando o fluxo de nutrição processa a pergunta
    Então a resposta deve ser `não sei`
    E deve incluir fonte ou indicar ausência de evidência
    E não deve inventar resposta
