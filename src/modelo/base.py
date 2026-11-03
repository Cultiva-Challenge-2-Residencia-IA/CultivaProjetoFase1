from typing import Protocol


class ModeloDeLinguagem(Protocol):
    """Contrato mínimo com qualquer modelo. Trocar de provedor não muda o grafo."""

    nome: str

    def gerar(self, sistema: str, mensagem: str) -> str: ...
