"""Roteador por palavras-chave: decide se a pergunta pertence a outra Aba."""

import re

from dominio.modelos import Aba
from dominio.texto import normalizar

# Cada termo é um trecho de regex aplicado depois de \b, sobre texto normalizado.
# Sem \b no fim, vale como prefixo ("aliment" casa "alimentos" e "alimentação").
_TERMOS: dict[Aba, tuple[str, ...]] = {
    Aba.NUTRICAO: (
        r"aliment",
        r"comer\b",
        r"comida",
        r"refeic",
        r"cafe da manha",
        r"almoc",
        r"jantar",
        r"lanche",
        r"fruta",
        r"verdura",
        r"legume",
        r"feijao",
        r"arroz",
        r"ultraprocessad",
        r"processad",
        r"cozinh",
        r"receita",
        r"dieta",
        r"calori",
        r"proteina",
        r"carboidrat",
        r"acucar",
        r"sal\b",
        r"gordura",
        r"jejum",
        r"nutri",
        r"refrigerante",
        r"mercado",
        r"feiras?\b",
        r"beliscar",
        r"fast-food",
        r"marmita",
        r"cardapio",
    ),
    Aba.SAUDE_FISICA: (
        r"treino",
        r"treinar",
        r"academia",
        r"musculac",
        r"corrida",
        r"correr\b",
        r"caminhada",
        r"caminhar",
        r"alongament",
        r"exercicio",
        r"agachament",
        r"flexao",
        r"abdominai",
        r"cardio",
        r"aerobic",
        r"hipertrofia",
        r"crossfit",
        r"pedalar",
        r"bicicleta",
        r"natacao",
        r"futebol",
        r"yoga",
        r"pilates",
    ),
    Aba.ESTUDOS: (
        r"estudar",
        r"estudos?\b",
        r"provas?\b",
        r"vestibular",
        r"enem\b",
        r"pomodoro",
        r"materias?\b",
        r"simulados?\b",
        r"revisao",
        r"tcc\b",
        r"aulas?\b",
        r"cronograma",
        r"concursos?\b",
        r"procrastin",
    ),
}


def _conta(texto: str, termos: tuple[str, ...]) -> int:
    return sum(1 for termo in termos if re.search(rf"\b{termo}", texto))


def aba_de_destino(mensagem: str, aba_atual: Aba) -> Aba | None:
    """Aba para onde redirecionar, ou None se a pergunta fica na Aba atual.

    Ficam na Aba atual: perguntas com algum termo dela e perguntas sem termo de nenhuma Aba.
    """
    texto = normalizar(mensagem)
    if _conta(texto, _TERMOS[aba_atual]):
        return None
    contagens = {aba: _conta(texto, termos) for aba, termos in _TERMOS.items() if aba != aba_atual}
    aba, total = max(contagens.items(), key=lambda par: par[1])
    return aba if total else None
