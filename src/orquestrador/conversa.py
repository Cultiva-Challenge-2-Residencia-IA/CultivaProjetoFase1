"""Conversa social (issue #99): saudação, agradecimento, despedida e "o que você faz?".

Não é pergunta de conteúdo: recebe uma resposta fixa que apresenta o CULTIVA, sem busca nem LLM.
Só vale para mensagem curta e sem termo de nenhuma área ("Olá, quero treinar perna" é pergunta).
"""

import re

from src.retrieval.hybrid_retriever import normalize_text

_SOCIAL = re.compile(
    r"^(oi+|ola|ole|opa|e ai|eai|hey|bom dia|boa tarde|boa noite|tudo bem|tudo bom|tudo certo|como vai"
    r"|obrigad[oa]|muito obrigad[oa]|valeu|brigad[oa]|agradeco|tchau|ate mais|ate logo|falou"
    r"|quem e voce|o que voce faz|o que voce sabe fazer|como (voce )?funciona|como voce pode me ajudar"
    r"|me ajuda|pode me ajudar|ajuda)\b"
)
_MAX_PALAVRAS = 8

APRESENTACOES = {
    "geral": (
        "Olá! Eu sou o assistente do CULTIVA. Respondo dúvidas sobre Nutrição e Saúde Física com base "
        "em fontes verificadas, como o Guia Alimentar para a População Brasileira e as diretrizes da OMS. "
        "Sobre o que você quer saber?"
    ),
    "nutricao": (
        "Olá! Este é o chat de Nutrição do CULTIVA. Respondo dúvidas sobre alimentação com base em fontes "
        "verificadas, como o Guia Alimentar para a População Brasileira. Sobre o que você quer saber?"
    ),
    "saude_fisica": (
        "Olá! Este é o chat de Saúde Física do CULTIVA. Respondo dúvidas sobre atividade física e exercício "
        "com base em fontes verificadas, como as diretrizes da OMS e o Guia de Atividade Física. Sobre o que "
        "você quer saber?"
    ),
}


def e_conversa_social(mensagem: str) -> bool:
    texto = normalize_text(mensagem).strip(" !?.,")
    return len(texto.split()) <= _MAX_PALAVRAS and bool(_SOCIAL.match(texto))
