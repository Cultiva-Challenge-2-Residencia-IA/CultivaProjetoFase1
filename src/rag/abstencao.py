"""Resposta "não sei" quando o corpus não tem evidência para a pergunta (RF-IA01, issue #6).

O sinal é a similaridade de cosseno do Trecho mais próximo no ChromaDB. A nota final do ranking
(RRF puro, desde a #35) depende só da posição nas listas e não serve para isso.

Limite conhecido: o cosseno mede se a pergunta é do mesmo assunto que algum Trecho, não se algum
Trecho a responde. Ele separa bem perguntas fora de Nutrição, mas não perguntas de Nutrição sobre
temas ausentes do corpus (kombucha, colágeno). Ver eval/abstencao/README.md.
"""

MENSAGEM_NAO_SEI = (
    "Não encontrei nas fontes aprovadas do CULTIVA informação para responder a essa pergunta. "
    "Eu só respondo com base em fontes verificadas sobre Nutrição, como o Guia Alimentar para a "
    "População Brasileira, para não arriscar uma informação sem respaldo.\n\n"
    "Se a dúvida for sobre a sua alimentação em particular, um nutricionista pode ajudar."
)


def sem_evidencia(similaridade_maxima: float, limiar: float) -> bool:
    """True quando nem o Trecho mais próximo chega ao limiar calibrado."""
    return similaridade_maxima < limiar
