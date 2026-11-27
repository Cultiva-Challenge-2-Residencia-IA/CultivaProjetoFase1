"""Filtro de relevância antes da síntese (corrective RAG local, issue #105).

A busca sempre devolve Trechos, mesmo quando nenhum trata da pergunta, e a síntese respondia com
eles: "Gostaria de treinar perna" trazia dor lombar, marcha e educação física escolar. O filtro dá a
cada Trecho a nota do cross-encoder (`src/retrieval/reranker_cruzado.py`) e só deixa ir à síntese
os Trechos com nota de pelo menos `FILTRO_RELEVANCIA_LIMIAR`. Se nenhum passar:

1. com o LLM local, a busca é reformulada uma vez (`reformular`): termos técnicos e, em Saúde
   Física, a pergunta em inglês, a língua de 16 das 18 fontes. O filtro julga a nova busca;
2. se ainda não houver Trecho relevante, a resposta é a lacuna explícita (`mensagem_lacuna`): diz
   que as fontes não tratam da pergunta e oferece os temas que elas cobrem, sem colar Trechos sem
   relação.

Ele é diferente do "não sei" do cosseno (`src/rag/abstencao.py`), que só vale fora do domínio: a
lacuna é para pergunta da área sem base nas fontes. O limiar e a decisão vêm do `dev` de
eval/relevancia/criterios.md.
"""

from dataclasses import dataclass, field
import json
from typing import Any, Callable, Dict, List, Optional, Sequence

from src.models.schemas import RetrievedChunk

LLMJson = Callable[[str, str], Optional[Dict[str, Any]]]

TEMAS_NUTRICAO = (
    "o Guia Alimentar para a População Brasileira e a alimentação saudável, alimentos "
    "ultraprocessados, dietas vegetarianas, sobrepeso e obesidade, jejum intermitente, suplementos e "
    "hidratação de quem se exercita, consumo de frutas e hortaliças, e a relação da alimentação com o "
    "sono e a ansiedade"
)
TEMAS_SAUDE_FISICA = (
    "quanto de atividade física cada idade precisa, treino de força, sedentarismo, aquecimento, carga "
    "de treino e risco de lesão ou de doença em atletas, e exercício na dor lombar e na ciática, na "
    "tendinopatia do ombro, na entorse de tornozelo, na dor patelofemoral e na artrose"
)
TEMAS_POR_AREA = {"nutricao": TEMAS_NUTRICAO, "saude_fisica": TEMAS_SAUDE_FISICA}
PROFISSIONAL_POR_AREA = {
    "nutricao": "um nutricionista",
    "saude_fisica": "um profissional de Educação Física ou um fisioterapeuta",
}


def mensagem_lacuna(area: str) -> str:
    """Resposta fixa quando nenhum Trecho trata da pergunta: a lacuna e o que as fontes cobrem."""
    temas = TEMAS_POR_AREA.get(area, TEMAS_NUTRICAO)
    profissional = PROFISSIONAL_POR_AREA.get(area, PROFISSIONAL_POR_AREA["nutricao"])
    return (
        "As fontes aprovadas do CULTIVA não tratam dessa pergunta: os trechos que a busca encontrou são "
        "sobre outros assuntos, e eu não vou responder com eles.\n\n"
        f"Nessas fontes, posso falar sobre {temas}. Se a sua dúvida tiver relação com algum desses "
        f"temas, pergunte de novo com mais detalhes.\n\n"
        f"Para uma orientação para o seu caso, procure {profissional}."
    )


@dataclass
class Julgamento:
    """Resultado do filtro: os Trechos que vão para a síntese e os descartados, com as notas."""

    mantidos: List[RetrievedChunk] = field(default_factory=list)
    descartados: List[RetrievedChunk] = field(default_factory=list)

    @property
    def lacuna(self) -> bool:
        return not self.mantidos


def julgar(consulta: str, recuperados: Sequence[RetrievedChunk], reranker: Any, limiar: float) -> Julgamento:
    """Dá a nota do cross-encoder para (consulta, Trecho) e separa pelo limiar, na ordem da busca.

    Sempre julga contra a `consulta`: com consultas extras fundidas por RRF, a nota que o reranker
    deu na busca pode ter sido contra outra consulta. Quando é a mesma, vem do cache do reranker."""
    notas = reranker.pontuar(
        consulta,
        [r.chunk.contextualized_text for r in recuperados],
        [r.chunk.chunk_id for r in recuperados],
    )
    julgamento = Julgamento()
    for item, nota in zip(recuperados, notas):
        julgado = item.model_copy(update={"relevancia": round(nota, 6)})
        (julgamento.mantidos if nota >= limiar else julgamento.descartados).append(julgado)
    return julgamento


SISTEMA_REFORMULACAO = """Você reformula buscas para um assistente de saúde. As fontes de "nutricao" estão em português; as de "saude_fisica" estão quase todas em inglês (diretrizes da OMS, ACSM, NICE, JOSPT).
A busca com a pergunta do usuário não achou trechos relevantes. Reescreva a pergunta como consultas de busca com os termos técnicos que uma diretriz usaria (por exemplo, "treinar perna" vira "lower body resistance training"; "dor nas costas" vira "low back pain").
Responda SÓ com JSON: {"consultas": ["...", "..."]}, com no máximo 3 consultas curtas, em inglês para saude_fisica e em português para nutricao. Não responda a pergunta."""


def reformular(pergunta: str, area: str, llm: Optional[LLMJson], maximo: int = 3) -> List[str]:
    """Consultas reformuladas pelo LLM local; sem LLM ou com saída inválida, nenhuma."""
    if llm is None:
        return []
    try:
        bruto = llm(SISTEMA_REFORMULACAO, json.dumps({"area": area, "pergunta": pergunta}, ensure_ascii=False))
    except Exception:  # Ollama fora ou tempo esgotado: segue sem reformular
        return []
    consultas = bruto.get("consultas") if isinstance(bruto, dict) else None
    if not isinstance(consultas, list):
        return []
    limpas = []
    for c in consultas:
        texto = str(c or "").strip()
        if texto and texto.lower() != pergunta.strip().lower() and texto not in limpas:
            limpas.append(texto)
    return limpas[:maximo]
