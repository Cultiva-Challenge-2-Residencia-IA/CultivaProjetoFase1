"""Reescrita de consulta numa chamada única ao LLM local (issue #99).

A chamada devolve, em JSON:

- `pergunta_completa`: a mensagem reescrita com o Histórico, para a pergunta de continuação
  ("e para quem tem hipertensão?") virar uma pergunta que se busca sozinha;
- `subperguntas`: uma por área envolvida (decomposição), cada uma com um `trecho_hipotetico` (HyDE):
  um parágrafo no estilo e no idioma das fontes da área, buscado junto com a pergunta original.

Sem LLM, ou com saída inválida, a reescrita usa a mensagem como veio e as áreas das regras
(`rotear_por_regras`), sem trecho hipotético: o mesmo caminho de antes, determinístico.

Projetor de contexto (issue #112): quando há Fatos do Usuário candidatos, a mesma chamada escolhe,
por Subpergunta, os ids dos fatos relacionados (`fatos`). Sem LLM, nenhum fato é escolhido (falha
fechada), e id que não está entre os candidatos é ignorado.
"""

from dataclasses import dataclass, field
import json
from typing import Any, Callable, Dict, List, Optional, Sequence

from src.orquestrador.roteamento import AREAS, rotear_por_regras

LLMJson = Callable[[str, str], Optional[Dict[str, Any]]]

SISTEMA_REESCRITA = """Você prepara buscas para um assistente de saúde com duas áreas:
- "nutricao": alimentação, nutrientes, dietas, suplementos, rótulos (fontes em português).
- "saude_fisica": atividade física, exercício, treino, dor e lesão musculoesquelética, reabilitação (fontes quase todas em inglês).

Receba o histórico recente e a mensagem nova. Responda SÓ com JSON:
{
  "pergunta_completa": "a mensagem nova reescrita para ser entendida sem o histórico (resolva 'e para quem...', 'isso', 'nesse caso')",
  "subperguntas": [
    {"area": "nutricao" ou "saude_fisica",
     "pergunta": "a parte da pergunta completa que é dessa área",
     "trecho_hipotetico": "um parágrafo curto (2 a 3 frases) como o de uma diretriz que responderia a essa parte; em inglês para saude_fisica e em português para nutricao"}
  ]
}
Regras: uma subpergunta por área envolvida, no máximo uma por área. Se a mensagem não for de nenhuma das duas áreas, devolva "subperguntas": []. Não responda a pergunta e não dê conselho individual; o trecho hipotético só serve para a busca."""

INSTRUCAO_FATOS = """

Você também recebe "fatos_candidatos": fatos que a própria pessoa contou sobre a vida dela, cada um com "id".
Em cada subpergunta, acrescente "fatos": a lista dos ids que se relacionam com aquela subpergunta e
ajudariam a relacionar a resposta à situação da pessoa (ex.: os treinos dela numa pergunta sobre proteína).
Escolha só o necessário; fato sem relação com a subpergunta fica de fora. Sem fato relacionado, "fatos": []."""


@dataclass
class Mensagem:
    """Uma mensagem do Histórico. `area` diz a área que respondeu (None quando não houve área)."""

    papel: str  # "usuario" ou "assistente"
    texto: str
    area: Optional[str] = None
    # Todas as áreas da mensagem (a do usuário pode ter ido às duas); `area` só quando é uma.
    areas: List[str] = field(default_factory=list)

    def e_da_area(self, area: str) -> bool:
        return self.area == area or area in self.areas


@dataclass
class Subpergunta:
    area: str
    texto: str
    trecho_hipotetico: Optional[str] = None
    # Ids dos Fatos do Usuário que o LLM escolheu para esta Subpergunta (Projetor de contexto).
    fatos_ids: List[int] = field(default_factory=list)


@dataclass
class Reescrita:
    pergunta_completa: str
    subperguntas: List[Subpergunta] = field(default_factory=list)
    origem: str = "regras"  # "llm" ou "regras"

    @property
    def areas(self) -> List[str]:
        return [s.area for s in self.subperguntas]


def _historico_em_texto(historico: Sequence[Mensagem]) -> str:
    linhas = [f"{'Usuário' if m.papel == 'usuario' else 'Assistente'}: {m.texto}" for m in historico]
    return "\n".join(linhas) if linhas else "(sem histórico)"


def _pelas_regras(mensagem: str, areas_permitidas: Sequence[str]) -> Reescrita:
    rota = rotear_por_regras(mensagem)
    return Reescrita(
        pergunta_completa=mensagem,
        subperguntas=[Subpergunta(area, mensagem) for area in rota.areas if area in areas_permitidas],
        origem="regras",
    )


def _validar(bruto: Any, mensagem: str, areas_permitidas: Sequence[str]) -> Optional[Reescrita]:
    if not isinstance(bruto, dict) or not isinstance(bruto.get("subperguntas"), list):
        return None
    completa = str(bruto.get("pergunta_completa") or "").strip() or mensagem
    subperguntas: List[Subpergunta] = []
    for item in bruto["subperguntas"]:
        if not isinstance(item, dict):
            continue
        area, texto = item.get("area"), str(item.get("pergunta") or "").strip()
        if area not in areas_permitidas or not texto or any(s.area == area for s in subperguntas):
            continue
        hipotetico = str(item.get("trecho_hipotetico") or "").strip() or None
        ids = []
        for valor in item.get("fatos") if isinstance(item.get("fatos"), list) else []:
            try:
                ids.append(int(valor))
            except (TypeError, ValueError):
                continue
        subperguntas.append(Subpergunta(area, texto, hipotetico, ids))
    return Reescrita(pergunta_completa=completa, subperguntas=subperguntas, origem="llm")


def reescrever(
    mensagem: str,
    historico: Sequence[Mensagem],
    llm: Optional[LLMJson],
    areas_permitidas: Sequence[str] = AREAS,
    fatos_candidatos: Sequence[Dict[str, Any]] = (),
) -> Reescrita:
    """Reescreve a mensagem; sem LLM ou com saída inválida, usa as regras (sem fatos escolhidos)."""
    if llm is not None:
        entrada: Dict[str, Any] = {"historico": _historico_em_texto(historico), "mensagem_nova": mensagem}
        sistema = SISTEMA_REESCRITA
        if fatos_candidatos:
            entrada["fatos_candidatos"] = list(fatos_candidatos)
            sistema += INSTRUCAO_FATOS
        usuario = json.dumps(entrada, ensure_ascii=False)
        try:
            reescrita = _validar(llm(sistema, usuario), mensagem, areas_permitidas)
        except Exception:  # LLM fora, tempo esgotado: vale o caminho determinístico
            reescrita = None
        if reescrita is not None:
            return reescrita
    return _pelas_regras(mensagem, areas_permitidas)
