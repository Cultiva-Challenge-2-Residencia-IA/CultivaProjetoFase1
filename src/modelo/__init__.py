"""Acesso a modelos de linguagem por uma interface própria."""

from config import Configuracao
from modelo.base import ModeloDeLinguagem
from modelo.falso import ModeloFalso
from modelo.ollama import ModeloOllama


def criar_modelo(config: Configuracao) -> ModeloDeLinguagem:
    """Cria o modelo a partir da configuração já validada."""
    if config.provedor == "ollama":
        return ModeloOllama(modelo=config["CULTIVA_MODELO"], url=config["CULTIVA_OLLAMA_URL"])
    if config.provedor == "falso":
        return ModeloFalso()
    raise ValueError(f"Provedor de modelo desconhecido: {config.provedor!r}")


__all__ = ["ModeloDeLinguagem", "ModeloFalso", "ModeloOllama", "criar_modelo"]
