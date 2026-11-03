"""Configuração do CULTIVA, lida do arquivo .env da raiz do repositório.

Não há valores padrão no código: se o .env ou alguma variável obrigatória faltar, os
pontos de entrada (chat, API e avaliação) não iniciam e dizem o que falta. Uma variável
já definida no ambiente tem prioridade sobre o .env. Os testes não usam este módulo:
eles injetam o modelo falso diretamente.
"""

import os
from dataclasses import dataclass
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
ARQUIVO_ENV = RAIZ / ".env"

# Variáveis obrigatórias para cada provedor, além de CULTIVA_PROVEDOR.
VARIAVEIS_POR_PROVEDOR: dict[str, tuple[str, ...]] = {
    "ollama": ("CULTIVA_MODELO", "CULTIVA_OLLAMA_URL"),
    "falso": (),
}


class ConfiguracaoInvalida(RuntimeError):
    pass


@dataclass(frozen=True)
class Configuracao:
    provedor: str
    valores: dict[str, str]
    origem: dict[str, str]  # variável -> "ambiente", ".env" ou "linha de comando"

    def __getitem__(self, chave: str) -> str:
        return self.valores[chave]


def ler_env(caminho: Path) -> dict[str, str]:
    valores: dict[str, str] = {}
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, valor = linha.split("=", 1)
        valores[chave.strip()] = valor.strip().strip('"').strip("'")
    return valores


def carregar_configuracao(caminho: Path = ARQUIVO_ENV, provedor: str | None = None) -> Configuracao:
    """Lê e valida a configuração. `provedor` (da linha de comando) vence o .env."""
    if not caminho.exists():
        raise ConfiguracaoInvalida(
            f"Arquivo {caminho.name} não encontrado em {caminho.parent}.\n"
            "Crie a partir do modelo: cp .env.example .env"
        )
    arquivo = ler_env(caminho)
    valores: dict[str, str] = {}
    origem: dict[str, str] = {}

    def buscar(chave: str) -> str | None:
        for fonte, dados in (("ambiente", os.environ), (".env", arquivo)):
            valor = dados.get(chave, "").strip()
            if valor:
                valores[chave], origem[chave] = valor, fonte
                return valor
        return None

    if provedor:
        valores["CULTIVA_PROVEDOR"], origem["CULTIVA_PROVEDOR"] = provedor, "linha de comando"
    else:
        provedor = buscar("CULTIVA_PROVEDOR")
    if not provedor:
        raise ConfiguracaoInvalida(_faltando(["CULTIVA_PROVEDOR"], caminho))
    provedor = provedor.lower()
    if provedor not in VARIAVEIS_POR_PROVEDOR:
        opcoes = ", ".join(sorted(VARIAVEIS_POR_PROVEDOR))
        raise ConfiguracaoInvalida(f"CULTIVA_PROVEDOR={provedor!r} inválido. Use: {opcoes}")

    faltando = [c for c in VARIAVEIS_POR_PROVEDOR[provedor] if buscar(c) is None]
    if faltando:
        raise ConfiguracaoInvalida(_faltando(faltando, caminho))
    return Configuracao(provedor=provedor, valores=valores, origem=origem)


def _faltando(chaves: list[str], caminho: Path) -> str:
    lista = "\n".join(f"  - {c}" for c in chaves)
    return f"Variáveis obrigatórias ausentes em {caminho.name}:\n{lista}\nVeja o .env.example."
