from dataclasses import dataclass
from pathlib import Path

import yaml

from dominio.modelos import Aba

_ARQUIVO = Path(__file__).with_name("allowlist.yaml")


class AllowlistInvalida(ValueError):
    pass


@dataclass(frozen=True)
class RegraDeAgente:
    perfil: frozenset[str]
    registros_das_abas: frozenset[Aba]
    metas_das_abas: frozenset[Aba]


def carregar_allowlist(caminho: Path = _ARQUIVO) -> dict[str, RegraDeAgente]:
    dados = yaml.safe_load(caminho.read_text(encoding="utf-8"))
    proibidos = set(dados.get("nunca", []))
    regras: dict[str, RegraDeAgente] = {}
    for agente, regra in dados["agentes"].items():
        campos = set(regra.get("perfil", []))
        if campos & proibidos:
            raise AllowlistInvalida(
                f"Agente {agente!r} pede campos proibidos: {sorted(campos & proibidos)}"
            )
        regras[agente] = RegraDeAgente(
            perfil=frozenset(campos),
            registros_das_abas=frozenset(Aba(a) for a in regra.get("registros_das_abas", [])),
            metas_das_abas=frozenset(Aba(a) for a in regra.get("metas_das_abas", [])),
        )
    return regras
