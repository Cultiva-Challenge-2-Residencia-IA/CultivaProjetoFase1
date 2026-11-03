"""Defesa de prompt injection por padrões (RNF04)."""

import re

from dominio.texto import normalizar

_PADROES = tuple(
    re.compile(p)
    for p in (
        r"\b(ignore|ignora|ignorar|desconsidere|esqueca)\b.{0,30}\b(instrucoes|regras|orientacoes|restricoes)\b",
        r"\b(mostre|mostra|revele|revela|repita|imprima|copie)\b.{0,30}\bprompt\b",
        r"\bprompt (do|de) sistema\b",
        r"\bsystem prompt\b",
        r"\bmodo (desenvolvedor|developer|dan)\b",
        r"\bjailbreak\b",
        r"\b(finja|aja como se)\b.{0,30}\bnao (tem|tivesse|houvesse)\b.{0,15}\b(regras|restricoes|limites)\b",
        r"\bdados (de|dos) outros? usuarios?\b",
        r"\bvoce agora e\b.{0,40}\bsem (regras|restricoes|limites)\b",
    )
)


def detectar_injecao(texto: str) -> bool:
    normalizado = normalizar(texto)
    return any(p.search(normalizado) for p in _PADROES)
