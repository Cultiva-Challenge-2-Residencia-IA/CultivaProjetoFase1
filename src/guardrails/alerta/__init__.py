"""Portão de sinal de alerta (issue #99): sintoma físico que pede atendimento, e não resposta.

Vale para todos os chats, logo depois do portão de risco (RF-IA03). Ele não cobre sofrimento
psíquico nem comportamento alimentar de risco, que são do portão de risco. A detecção é por
expressões, escritas a partir dos sinais de interrupção de exercício das diretrizes (dor no
peito, desmaio, falta de ar desproporcional, palpitação com tontura, lesão aguda), e não a partir
de casos de avaliação.
"""

import re
from typing import List

from src.retrieval.hybrid_retriever import normalize_text

MENSAGEM_ALERTA = (
    "O que você descreveu pode ser um sinal de alerta. Se estiver acontecendo agora, pare a "
    "atividade e procure atendimento: em caso de dor no peito, desmaio ou falta de ar intensa, "
    "ligue para o SAMU (192) ou vá a um pronto-socorro.\n\n"
    "Eu não avalio sintomas nem lesões. Um médico ou fisioterapeuta pode examinar o seu caso "
    "antes de você voltar a treinar."
)

# "Quebrei" e "apaguei" só contam com contexto de corpo ou de queda: "quebrei a dieta",
# "quebrei meu recorde" e "apaguei o app" não são sinal de alerta.
_PARTE_DO_CORPO = (r"(o |a |os |as |meu |minha |um |uma )?(braco|perna|pe|mao|dedo|punho|tornozelo|joelho|"
                   r"cotovelo|ombro|clavicula|costela|nariz|quadril|osso|tibia|femur|canela)s?")
_APAGUEI_COM_CONTEXTO = (r"apaguei (e |e ca\w*|na |no |durante|depois|correndo|treinando|pedalando|nadando|"
                         r"de repente|por alguns)|ca\w* e apaguei")

_INTENSO = r"(forte|fortes|muit[oa]|intens[oa]|anormal|desproporcional|nao consigo respirar|sufoc\w*)"

SINAIS_DE_ALERTA = [
    ("dor_no_peito", re.compile(r"\b(dor|aperto|pressao|queimacao)\w* (forte |intensa )?no peito\b")),
    ("desmaio", re.compile(rf"\b(desmai\w*|perdi (os )?sentidos|{_APAGUEI_COM_CONTEXTO})\b")),
    ("falta_de_ar", re.compile(rf"\bfalta de ar\b.*\b{_INTENSO}\b|\b{_INTENSO}\b.*\bfalta de ar\b")),
    ("palpitacao_com_tontura", re.compile(
        r"\b(palpita\w*|coracao disparad\w*|coracao acelerad\w*)\b.*\b(tontura|tont[oa]|vista escur\w*)\b"
        r"|\b(tontura|tont[oa]|vista escur\w*)\b.*\b(palpita\w*|coracao disparad\w*|coracao acelerad\w*)\b")),
    ("lesao_aguda", re.compile(
        r"\b(torci|tor[cç]\w* o|estal\w*|rompi\w*|ouvi um estalo)\b.*\b(inch\w*|roxo|nao consigo (apoiar|pisar|mexer|andar|dobrar))\b"
        rf"|\b(fratur\w*|quebrei {_PARTE_DO_CORPO})\b")),
]


def detectar_sinal_de_alerta(texto: str) -> List[str]:
    """Nomes dos sinais de alerta encontrados no texto; lista vazia quando não há nenhum."""
    norm = normalize_text(texto)
    return [nome for nome, padrao in SINAIS_DE_ALERTA if padrao.search(norm)]
