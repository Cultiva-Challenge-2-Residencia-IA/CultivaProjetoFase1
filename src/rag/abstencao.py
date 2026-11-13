"""Resposta "não sei" para perguntas fora do domínio de Nutrição (RF-IA01, issue #6).

Dois sinais, e o "não sei" só vem quando os dois apontam para fora do domínio:

1. o cosseno do Trecho mais próximo no ChromaDB fica abaixo do limiar; e
2. a pergunta não tem nenhum termo do vocabulário de Nutrição (`TERMOS_NUTRICAO`).

O cosseno sozinho recusava perguntas que o corpus responde: o modelo de embeddings vai mal com
perguntas curtas ("Jejum intermitente funciona?" tem 0,24, e o BM25 acha a resposta em Azevedo
et al.). O vocabulário só impede recusas: um termo que falte na lista, no pior caso, deixa recusar
uma pergunta de cosseno baixo.

Limite conhecido: temas de Nutrição ausentes do corpus (kombucha, colágeno) continuam sendo
respondidos. Ver eval/abstencao/README.md e a issue #52.
"""

import re

from src.retrieval.hybrid_retriever import normalize_text

MENSAGEM_NAO_SEI = (
    "Não encontrei nas fontes aprovadas do CULTIVA informação para responder a essa pergunta. "
    "Eu só respondo com base em fontes verificadas sobre Nutrição, como o Guia Alimentar para a "
    "População Brasileira, para não arriscar uma informação sem respaldo.\n\n"
    "Se a dúvida for sobre a sua alimentação em particular, um nutricionista pode ajudar."
)

# Vocabulário do domínio, aplicado ao texto em minúsculas e sem acentos. Escrito a partir do domínio,
# não dos casos de avaliação. Na dúvida, inclua: um termo a mais só evita uma recusa.
TERMOS_NUTRICAO = re.compile(
    r"\b(aliment\w*|comer|come|comem|comendo|comi|comida\w*|refeic\w*|dieta\w*|nutri\w*|caloria\w*|kcal"
    r"|proteic\w*|proteina\w*|carboidrat\w*|gordura\w*|lipid\w*|acucar\w*|adocante\w*|sal|sodio|vitamina\w*"
    r"|minera\w*|ferro|calcio|zinco|magnesio|potassio|fibra\w*|jejum|emagrec\w*|engord\w*|peso|obes\w*|fome"
    r"|saciedade|apetite|bebida\w*|beber|bebo|agua|hidrat\w*|suplement\w*|whey|creatina|bcaa"
    r"|ultraprocessad\w*|processad\w*|in natura|fruta\w*|verdura\w*|legume\w*|hortalic\w*|feijao|arroz"
    r"|carne\w*|leite|ovo\w*|cozinh\w*|receita\w*|cardapio\w*|lanche\w*|lanchar|cafe|cha|refrigerante\w*"
    r"|rotulo\w*|digest\w*|intestin\w*|glicemi\w*|diabet\w*|colesterol|metabolism\w*|vegetarian\w*|vegan\w*"
    r"|cetogenic\w*|low carb|gluten|lactose|probiotic\w*|oleo\w*|azeite|castanha\w*|graos?|cereal\w*"
    r"|tempero\w*|curcuma|acafrao|pimenta\w*|absorc\w*|biodisponib\w*|sono|dormir)\b"
)


def tem_termo_de_nutricao(pergunta: str) -> bool:
    return bool(TERMOS_NUTRICAO.search(normalize_text(pergunta)))


def fora_do_dominio(pergunta: str, similaridade_maxima: float, limiar: float) -> bool:
    """True só quando o cosseno fica abaixo do limiar e a pergunta não tem termo de Nutrição."""
    return similaridade_maxima < limiar and not tem_termo_de_nutricao(pergunta)
