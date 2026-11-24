"""Roteamento do Chat geral por regras (issue #99).

As regras decidem os casos claros, sem LLM, para o CI e o benchmark serem determinísticos: o
vocabulário de cada área conta, e a mensagem vai para a área ou as áreas com termo. Sem termo de
nenhuma área, a rota fica indecisa: o Orquestrador pede a decisão ao LLM local, quando há, ou
segue o comportamento anterior (Agente de Nutrição, que dá o "não sei" fora do domínio). Os
vocabulários foram escritos a partir das áreas, não dos casos de avaliação; termos que as duas
áreas usam do mesmo jeito ("peso", "sono") ficam de fora, para não acionar as duas à toa.
"""

from dataclasses import dataclass, field
import re
from typing import List

from src.retrieval.hybrid_retriever import normalize_text

AREA_NUTRICAO = "nutricao"
AREA_SAUDE_FISICA = "saude_fisica"
AREAS = (AREA_NUTRICAO, AREA_SAUDE_FISICA)

TERMOS_DE_ROTA_NUTRICAO = re.compile(
    r"\b(aliment\w*|comer|come|comem|comendo|comi|comida\w*|refeic\w*|dieta\w*|nutri\w*|caloria\w*|kcal"
    r"|proteic\w*|proteina\w*|carboidrat\w*|gordura\w*|lipid\w*|acucar\w*|adocante\w*|sal|sodio|vitamina\w*"
    r"|minera\w*|ferro|calcio|zinco|magnesio|potassio|fibra\w*|jejum|fome|saciedade|apetite|bebida\w*"
    r"|suplement\w*|whey|creatina|bcaa|ultraprocessad\w*|in natura|fruta\w*|verdura\w*|legume\w*"
    r"|hortalic\w*|feijao|arroz|carne\w*|leite|ovo\w*|cozinh\w*|receita\w*|cardapio\w*|lanche\w*|lanchar"
    r"|cafe|cha|refrigerante\w*|rotulo\w*|digest\w*|intestin\w*|glicemi\w*|diabet\w*|colesterol"
    r"|vegetarian\w*|vegan\w*|cetogenic\w*|low carb|gluten|lactose|probiotic\w*|oleo\w*|azeite|castanha\w*"
    r"|cereal\w*|tempero\w*)\b"
)

TERMOS_DE_ROTA_SAUDE_FISICA = re.compile(
    r"\b(exercic\w*|atividades? fisicas?|treino\w*|treinar|treinando|musculac\w*|academia|corrida\w*|correr"
    r"|corro|caminhad\w*|caminhar|alongament\w*|alongar|aquecimento|aquecer|series?|repetic\w*|agachament\w*"
    r"|flexo\w*|abdominai?s?|prancha|aerobic\w*|anaerobic\w*|sedentar\w*|lesao|lesoes|lesion\w*|lombar"
    r"|lombalgia|ciatic\w*|tendin\w*|entorse\w*|tornozelo\w*|joelho\w*|ombro\w*|manguito|coluna|postura"
    r"|reabilit\w*|fisioterap\w*|esporte\w*|atleta\w*|condicionamento|frequencia cardiaca|intensidade"
    r"|hiit|pilates|yoga|ioga|natacao|nadar|bicicleta|bike|pedal\w*|ciclismo|artrose|osteoartrit\w*"
    r"|patelofemoral|hipertrofia|musculo\w*|muscular\w*|overtraining|carga de treino)\b"
)

TERMOS_DE_ESTUDOS = re.compile(
    r"\b(estud\w*|provas?|faculdade|vestibular|enem|concurso\w*|materia\w*|aulas?|tcc|flashcards?"
    r"|cronograma de estudo\w*|semestre|disciplina\w*)\b"
)


@dataclass
class Rota:
    """Áreas da mensagem pelas regras. `decidida` só quando uma única área tem termo."""

    areas: List[str] = field(default_factory=list)
    estudos: bool = False

    @property
    def decidida(self) -> bool:
        return len(self.areas) == 1


def areas_com_termo(texto: str) -> List[str]:
    norm = normalize_text(texto)
    areas = []
    if TERMOS_DE_ROTA_NUTRICAO.search(norm):
        areas.append(AREA_NUTRICAO)
    if TERMOS_DE_ROTA_SAUDE_FISICA.search(norm):
        areas.append(AREA_SAUDE_FISICA)
    return areas


def rotear_por_regras(mensagem: str) -> Rota:
    areas = areas_com_termo(mensagem)
    estudos = not areas and bool(TERMOS_DE_ESTUDOS.search(normalize_text(mensagem)))
    return Rota(areas=areas, estudos=estudos)
