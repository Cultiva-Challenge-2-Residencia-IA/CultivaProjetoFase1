"""Reescrita de consulta numa chamada única ao LLM local (issue #99).

A chamada devolve, em JSON:

- `pergunta_completa`: a mensagem reescrita com o Histórico, para a pergunta de continuação
  ("e para quem tem hipertensão?") virar uma pergunta que se busca sozinha;
- `subperguntas`: uma por área envolvida (decomposição), cada uma com um `trecho_hipotetico` (HyDE):
  um parágrafo no estilo e no idioma das fontes da área, buscado junto com a pergunta original.

Sem LLM, ou com saída inválida, a reescrita usa a mensagem como veio e as áreas das regras
(`rotear_por_regras`), sem trecho hipotético: o mesmo caminho de antes, determinístico.
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


@dataclass
class Mensagem:
    """Uma mensagem do Histórico. `area` diz a área que respondeu (None quando não houve área)."""

    papel: str  # "usuario" ou "assistente"
    texto: str
    area: Optional[str] = None


@dataclass
class Subpergunta:
    area: str
    texto: str
    trecho_hipotetico: Optional[str] = None


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
        subperguntas.append(Subpergunta(area, texto, hipotetico))
    return Reescrita(pergunta_completa=completa, subperguntas=subperguntas, origem="llm")


def reescrever(
    mensagem: str,
    historico: Sequence[Mensagem],
    llm: Optional[LLMJson],
    areas_permitidas: Sequence[str] = AREAS,
) -> Reescrita:
    """Reescreve a mensagem; sem LLM ou com saída inválida, usa as regras."""
    if llm is not None:
        usuario = json.dumps(
            {"historico": _historico_em_texto(historico), "mensagem_nova": mensagem}, ensure_ascii=False
        )
        try:
            reescrita = _validar(llm(SISTEMA_REESCRITA, usuario), mensagem, areas_permitidas)
        except Exception:  # LLM fora, tempo esgotado: vale o caminho determinístico
            reescrita = None
        if reescrita is not None:
            return reescrita
    return _pelas_regras(mensagem, areas_permitidas)
