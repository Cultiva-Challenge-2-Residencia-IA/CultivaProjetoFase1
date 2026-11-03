"""Portão de risco: detecta sinal de sofrimento por regras e léxico em pt-BR."""

import re
from dataclasses import dataclass
from functools import cache
from pathlib import Path

import yaml

from dominio.texto import normalizar

_LEXICO = Path(__file__).with_name("lexico.yaml")


@dataclass(frozen=True)
class ResultadoRisco:
    disparou: bool
    categorias: tuple[str, ...] = ()


@cache
def _padroes() -> dict[str, tuple[re.Pattern[str], ...]]:
    dados = yaml.safe_load(_LEXICO.read_text(encoding="utf-8"))
    return {
        categoria: tuple(re.compile(p) for p in padroes)
        for categoria, padroes in dados["categorias"].items()
    }


def avaliar_risco(texto: str) -> ResultadoRisco:
    normalizado = normalizar(texto)
    categorias = tuple(
        categoria
        for categoria, padroes in _padroes().items()
        if any(p.search(normalizado) for p in padroes)
    )
    return ResultadoRisco(disparou=bool(categorias), categorias=categorias)
