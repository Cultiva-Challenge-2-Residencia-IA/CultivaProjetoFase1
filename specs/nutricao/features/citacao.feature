# language: pt

Funcionalidade: citação de fontes
  Cenário: a resposta deve citar fontes recuperadas
    Dado que a pergunta tem resposta suportada pelo corpus
    Quando o fluxo de nutrição processa a pergunta
    Então a resposta deve incluir fonte e citação
    E cada afirmação deve apontar ao menos um `source_id`
    E a resposta deve identificar a IA e o nível de confiança
