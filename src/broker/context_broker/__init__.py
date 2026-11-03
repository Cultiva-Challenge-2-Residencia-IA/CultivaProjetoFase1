from dataclasses import dataclass, field

from broker.allowlist_campos import RegraDeAgente, carregar_allowlist
from dominio.modelos import Aba, Perfil, Registro


class AgenteSemPermissao(LookupError):
    pass


@dataclass(frozen=True)
class ContextoDoAgente:
    perfil: dict[str, tuple[str, ...]] = field(default_factory=dict)
    registros: tuple[Registro, ...] = ()
    metas: dict[Aba, tuple[str, ...]] = field(default_factory=dict)


class ContextBroker:
    def __init__(self, regras: dict[str, RegraDeAgente] | None = None):
        self._regras = regras if regras is not None else carregar_allowlist()

    def contexto_para(
        self, agente: str, perfil: Perfil, registros: tuple[Registro, ...]
    ) -> ContextoDoAgente:
        regra = self._regras.get(agente)
        if regra is None:
            raise AgenteSemPermissao(f"Agente sem allowlist: {agente!r}")
        return ContextoDoAgente(
            perfil={campo: getattr(perfil, campo) for campo in sorted(regra.perfil)},
            registros=tuple(r for r in registros if r.aba in regra.registros_das_abas),
            metas={
                aba: metas for aba, metas in perfil.metas.items() if aba in regra.metas_das_abas
            },
        )
