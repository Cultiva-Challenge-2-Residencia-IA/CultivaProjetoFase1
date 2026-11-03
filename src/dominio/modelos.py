from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum


class Aba(StrEnum):
    NUTRICAO = "nutricao"
    SAUDE_FISICA = "saude_fisica"
    ESTUDOS = "estudos"

    @property
    def nome_exibicao(self) -> str:
        return {
            Aba.NUTRICAO: "Nutrição",
            Aba.SAUDE_FISICA: "Saúde Física",
            Aba.ESTUDOS: "Estudos",
        }[self]


@dataclass(frozen=True)
class Registro:
    """Informação da rotina que o usuário salvou depois de confirmar."""

    aba: Aba
    data: date
    descricao: str


@dataclass(frozen=True)
class Perfil:
    nome: str
    email: str
    telefone: str = ""
    preferencias_alimentares: tuple[str, ...] = ()
    restricoes_alimentares: tuple[str, ...] = ()
    metas: dict[Aba, tuple[str, ...]] = field(default_factory=dict)


@dataclass(frozen=True)
class Trecho:
    """Pedaço de uma Fonte, citável por página."""

    id: str
    fonte_id: str
    titulo_fonte: str
    pagina_pdf: int
    texto: str
