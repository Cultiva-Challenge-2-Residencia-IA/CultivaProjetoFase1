"""Verificação de citações: a resposta precisa citar ao menos um Trecho recuperado."""

import re

_CITACAO = re.compile(r"\[([a-z0-9][a-z0-9-]*)\]")


def extrair_citacoes(texto: str) -> list[str]:
    vistos: list[str] = []
    for cid in _CITACAO.findall(texto):
        if cid not in vistos:
            vistos.append(cid)
    return vistos


def citacoes_validas(texto: str, ids_recuperados: set[str] | frozenset[str]) -> list[str]:
    """Citações do texto que apontam para Trechos recuperados. Vazia se alguma for inválida."""
    citadas = extrair_citacoes(texto)
    if not citadas or any(c not in ids_recuperados for c in citadas):
        return []
    return citadas


def remover_citacoes(texto: str) -> str:
    return re.sub(r"\s*\[[a-z0-9][a-z0-9-]*\]", "", texto).strip()
