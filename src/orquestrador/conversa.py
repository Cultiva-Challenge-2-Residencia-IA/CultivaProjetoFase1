"""Conversa social (issue #99): saudação, "tudo bem?", agradecimento, despedida e "o que você faz?".

Não é pergunta de conteúdo: não passa por busca nem por Agente de área. Dois caminhos:

- **LLM (preferido):** a chamada de reescrita, que já roda a cada mensagem, reconhece a conversa
  social em qualquer forma ("salve", "como vc tá?", gíria, erro de digitação) e escreve uma resposta
  curta no tom da pessoa. A resposta só é usada se passar em `resposta_social_valida`: curta, sem
  números, sem termo de nenhuma área (não traz conteúdo sem fonte, RN01 a RN04) e sem pedir dado
  pessoal. O convite para perguntar sobre a área do chat é acrescentado por código.
- **Regras (reserva):** sem LLM, com resposta inválida, ou na primeira mensagem da Conversa (para a
  saudação inicial não esperar o LLM), as regras abaixo reconhecem as formas comuns e a resposta é fixa.

Só vale para mensagem sem termo de nenhuma área ("Olá, quero treinar perna" é pergunta).
"""

import re
from typing import Optional

from src.orquestrador.roteamento import TERMOS_DE_ESTUDOS, rotear_por_regras
from src.retrieval.hybrid_retriever import normalize_text

TIPOS_SOCIAIS = ("saudacao", "como_vai", "agradecimento", "despedida", "apresentacao", "outro")

_REGRAS = (
    ("como_vai", r"tudo (bem|bom|certo|joia|tranquilo|em ordem)|td (bem|bom|certo|joia)|como vai"
                 r"|como (voce|vc|ce|tu) (esta|ta|vai|anda)|como (esta|ta)( voce| vc)?|e (voce|vc)"),
    ("saudacao", r"oi+|ola+|ole|opa|e ai|eai|eae|hey|salve|fala( ai)?|bom dia|boa tarde|boa noite"
                 r"|beleza|blz|suave|tranquilo"),
    ("agradecimento", r"obrigad[oa]|muito obrigad[oa]|valeu|vlw|brigad[oa]|agradeco|show( de bola)?"),
    ("despedida", r"tchau|ate mais|ate logo|ate amanha|falou|flw|fui"),
    ("apresentacao", r"quem e (voce|vc)|o que (voce|vc) faz|o que (voce|vc) sabe fazer|como (voce |vc )?funciona"
                     r"|como (voce|vc) pode me ajudar|me ajuda|pode me ajudar|ajuda"),
)
_MAX_PALAVRAS = 8
MAX_CARACTERES_RESPOSTA = 200

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
CONVITES = {
    "geral": "Quer tirar alguma dúvida sobre alimentação ou atividade física?",
    "nutricao": "Quer tirar alguma dúvida sobre alimentação?",
    "saude_fisica": "Quer tirar alguma dúvida sobre atividade física?",
}
RESPOSTAS_FIXAS = {
    "saudacao": "Oi!",
    "como_vai": "Tudo certo por aqui, obrigado por perguntar!",
    "agradecimento": "Por nada!",
    "despedida": "Até mais! Quando quiser, é só voltar.",
    "outro": "Certo!",
}

_DADO_PESSOAL = re.compile(
    r"\b(peso|idade|quantos anos|altura|imc|exames?|medicament\w*|remedios?|diagnostic\w*|doenca|dor)\b")


def tipo_social(mensagem: str) -> Optional[str]:
    """Tipo de conversa social reconhecido pelas regras, ou None (inclusive com termo de área)."""
    texto = re.sub(r"[^\w\s]", " ", normalize_text(mensagem))
    texto = " ".join(texto.split())
    if not texto or len(texto.split()) > _MAX_PALAVRAS or rotear_por_regras(mensagem).areas:
        return None
    for tipo, padrao in _REGRAS:
        if re.match(rf"^({padrao})\b", texto):
            return tipo
    return None


def e_conversa_social(mensagem: str) -> bool:
    return tipo_social(mensagem) is not None


def resposta_social_valida(texto: object) -> Optional[str]:
    """Resposta social escrita pelo LLM, se for só conversa: curta, sem número, sem termo de área
    (nem de Estudos) e sem pedir dado pessoal. Senão, None, e vale a resposta fixa."""
    if not isinstance(texto, str):
        return None
    texto = " ".join(texto.split())
    norm = normalize_text(texto)
    if (not texto or len(texto) > MAX_CARACTERES_RESPOSTA or re.search(r"\d", texto)
            or rotear_por_regras(texto).areas or TERMOS_DE_ESTUDOS.search(norm) or _DADO_PESSOAL.search(norm)):
        return None
    return texto


def resposta_social(chat: str, tipo: str, primeira: bool, escrita: Optional[str] = None) -> str:
    """Texto final: na primeira mensagem da Conversa, ou quando pedem para o assistente se apresentar,
    a apresentação do chat; nas demais, a resposta curta (do LLM ou fixa) e o convite do chat."""
    if primeira or tipo == "apresentacao":
        apresentacao = APRESENTACOES[chat]
        if escrita and tipo != "apresentacao":
            return f"{escrita} {apresentacao.removeprefix('Olá! ')}"
        return apresentacao
    corpo = escrita or RESPOSTAS_FIXAS.get(tipo, RESPOSTAS_FIXAS["outro"])
    if tipo == "despedida" or corpo.endswith("?"):
        return corpo
    return f"{corpo} {CONVITES[chat]}"
