"""Perfil e Registros fictícios, em memória, usados pela API e pela avaliação nesta fase.

A persistência real dos Registros fica para uma próxima branch.
"""

from datetime import date

from dominio.modelos import Aba, Perfil, Registro

PERFIL_EXEMPLO = Perfil(
    nome="Pessoa Exemplo",
    email="pessoa.exemplo@example.com",
    telefone="(61) 99999-0000",
    preferencias_alimentares=("comida caseira",),
    restricoes_alimentares=("vegetariana",),
    metas={
        Aba.NUTRICAO: ("almoçar todos os dias",),
        Aba.SAUDE_FISICA: ("caminhar 3 vezes por semana",),
        Aba.ESTUDOS: ("estudar 2 horas por dia",),
    },
)

REGISTROS_EXEMPLO = (
    Registro(Aba.NUTRICAO, date(2026, 11, 2), "Almoço com arroz, feijão e salada"),
    Registro(Aba.NUTRICAO, date(2026, 11, 3), "Pulei o café da manhã"),
    Registro(Aba.SAUDE_FISICA, date(2026, 11, 2), "Caminhada de 20 minutos, cansaço alto"),
    Registro(Aba.ESTUDOS, date(2026, 11, 3), "Estudei 2 horas para a prova"),
)
