"""Acesso a modelos de linguagem por uma interface própria."""

import os

from modelo.base import ModeloDeLinguagem
from modelo.falso import ModeloFalso
from modelo.ollama import ModeloOllama


def criar_modelo(provedor: str | None = None) -> ModeloDeLinguagem:
    """Cria o modelo pelo nome do provedor ou pela variável CULTIVA_PROVEDOR."""
    nome = (provedor or os.environ.get("CULTIVA_PROVEDOR", "ollama")).lower()
    if nome == "ollama":
        return ModeloOllama()
    if nome == "falso":
        return ModeloFalso()
    raise ValueError(f"Provedor de modelo desconhecido: {nome!r}")


__all__ = ["ModeloDeLinguagem", "ModeloFalso", "ModeloOllama", "criar_modelo"]
