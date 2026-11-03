"""Bloqueio de diagnóstico e prescrição (RN01, RN03, RF-IA02).

Duas checagens: o pedido do usuário (entrada) e o texto gerado pelo modelo (saída).
"""

import re

from dominio.texto import normalizar

_MEDICAMENTOS = (
    r"remedio|medicamento|suplemento|anabolizante|termogenico|ozempic|semaglutida|"
    r"sibutramina|orlistat|tirzepatida|diuretico|laxante|anfetamina|inibidor de apetite"
)

_PEDIDO = tuple(
    re.compile(p)
    for p in (
        rf"\b({_MEDICAMENTOS})s?\b",
        r"\bprotocolo\b",
        r"\b(dieta|cardapio)s? (fechad|exat|de \d)",
        r"\b(perder|emagrecer|secar|eliminar) \d+ ?(kg|quilos?)\b",
        r"\bdoses?\b",
        r"\b\d+ ?(mg|miligramas?)\b",
        r"\bquant[oa]s? (mg|miligramas?)\b",
        r"\b(devo|posso|preciso) tomar\b.{0,30}\b(vitamina|cafeina|creatina|whey|capsula|comprimido)",
        r"\bdiagnostic",
        r"\bo que (eu )?tenho\b",
        r"\be (sintoma|sinal) de\b",
        r"\b(sinto|tenho|estou com) (uma )?dor\b",
    )
)

_SAIDA = tuple(
    re.compile(p)
    for p in (
        rf"\b(tome|tomar|use|usar|recomendo)\b.{{0,40}}\b({_MEDICAMENTOS})s?\b",
        r"\b\d+ ?(mg|miligramas?|comprimidos?|capsulas?)\b",
        r"\bdieta de \d+ ?(kcal|calorias)\b",
        r"\b(coma|consuma|ingira) exatamente\b",
        r"\bvoce (tem|esta com|sofre de)\b.{0,20}\b(diabetes|anemia|depressao|ansiedade|"
        r"transtorno|hipertensao|gastrite|intolerancia|compulsao)\b",
        r"\bseu diagnostico\b",
    )
)


def pedido_fora_de_escopo(texto: str) -> bool:
    normalizado = normalizar(texto)
    return any(p.search(normalizado) for p in _PEDIDO)


def contem_prescricao(texto: str) -> bool:
    normalizado = normalizar(texto)
    return any(p.search(normalizado) for p in _SAIDA)
