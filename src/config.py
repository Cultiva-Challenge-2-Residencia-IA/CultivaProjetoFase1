"""Carga do arquivo .env da raiz do repositório.

Variáveis já definidas no ambiente têm prioridade sobre o .env.
"""

import os
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]


def carregar_env(caminho: Path = RAIZ / ".env") -> None:
    if not caminho.exists():
        return
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, valor = linha.split("=", 1)
        os.environ.setdefault(chave.strip(), valor.strip().strip('"').strip("'"))
