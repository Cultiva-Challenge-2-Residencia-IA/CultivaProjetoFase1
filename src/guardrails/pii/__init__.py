"""Mascaramento de dados pessoais antes do envio ao modelo (RNF05)."""

import re

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+")
_CPF = re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")
_TELEFONE = re.compile(r"(\(?\b\d{2}\)?\s?)?\b9?\d{4}[-\s]?\d{4}\b")


def mascarar_pii(texto: str, nomes: tuple[str, ...] = ()) -> str:
    """Troca e-mail, CPF, telefone e os nomes informados por marcadores."""
    mascarado = _EMAIL.sub("[EMAIL]", texto)
    mascarado = _CPF.sub("[CPF]", mascarado)
    mascarado = _TELEFONE.sub("[TELEFONE]", mascarado)
    for nome in nomes:
        for parte in (nome, *nome.split()):
            if len(parte) >= 3:
                mascarado = re.sub(
                    rf"\b{re.escape(parte)}\b", "[NOME]", mascarado, flags=re.IGNORECASE
                )
    return mascarado
