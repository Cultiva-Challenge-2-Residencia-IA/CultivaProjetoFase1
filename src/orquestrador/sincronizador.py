"""Sincronizador (RF-IA09, issue #99): cruza as respostas dos Agentes de área numa só.

O LLM recebe a pergunta, as respostas já citadas de cada agente e os Trechos que elas citam,
renumerados num só intervalo ([T1]..[Tn]). Ele escreve a resposta única no mesmo formato da
citação por frase (prompt v4), e a mesma checagem confere: cada frase precisa de uma citação
copiada de um Trecho entregue. Se alguma frase vier sem citação literal (fato que os agentes não
trouxeram), se a checagem reprovar ou se não houver LLM, as respostas ficam lado a lado, cada uma
com as suas citações, renumeradas.
"""

from dataclasses import dataclass, field
import json
import re
from typing import Any, Callable, Dict, List, Optional, Sequence

from src.models.schemas import RetrievedChunk
from src.rag.verificador.citacoes import (
    filtrar_citacoes_literais,
    normalizar_frases_citadas,
    verificar_citacoes,
)

LLMJson = Callable[[str, str], Optional[Dict[str, Any]]]

NOMES_DAS_AREAS = {"nutricao": "Nutrição", "saude_fisica": "Saúde Física"}
MARCADOR_T = re.compile(r"\[T(\d+)\]")

SISTEMA_SINCRONIZADOR = """Você junta as respostas de dois especialistas (Nutrição e Saúde Física) numa resposta única para a mesma pergunta.
Use SÓ o que as respostas e os trechos dizem. Não acrescente fato, número ou recomendação que não esteja nos trechos. Cruze as informações quando elas se completam (por exemplo, alimentação e exercício para o mesmo objetivo), sem prescrever nada a uma pessoa.
Responda SÓ com JSON: {"evidence_summary": [{"frase": "...", "trechos": [números dos trechos], "citacao": "pedaço COPIADO SEM ALTERAR (pelo menos 5 palavras seguidas) de um desses trechos"}]}
Escreva em português; a citação fica no idioma do trecho."""


@dataclass
class RespostaDeArea:
    area: str
    texto: str
    trechos: List[RetrievedChunk] = field(default_factory=list)


@dataclass
class Sincronizacao:
    texto: str
    modo: str  # "area_unica", "integrada" ou "lado_a_lado"
    trechos: List[RetrievedChunk] = field(default_factory=list)


def _renumerar(texto: str, deslocamento: int) -> str:
    return MARCADOR_T.sub(lambda m: f"[T{int(m.group(1)) + deslocamento}]", texto)


def _lado_a_lado(respostas: Sequence[RespostaDeArea]) -> Sincronizacao:
    partes, trechos = [], []
    for r in respostas:
        partes.append(f"**{NOMES_DAS_AREAS.get(r.area, r.area)}**\n{_renumerar(r.texto, len(trechos))}")
        trechos.extend(r.trechos)
    return Sincronizacao(texto="\n\n".join(partes), modo="lado_a_lado", trechos=trechos)


def sincronizar(pergunta: str, respostas: Sequence[RespostaDeArea], llm: Optional[LLMJson]) -> Sincronizacao:
    if len(respostas) < 2:
        unica = respostas[0] if respostas else RespostaDeArea(area="", texto="")
        return Sincronizacao(texto=unica.texto, modo="area_unica", trechos=list(unica.trechos))
    lado_a_lado = _lado_a_lado(respostas)
    if llm is None or not all(r.trechos for r in respostas):
        return lado_a_lado
    fontes = {f"T{i}": t.chunk.raw_text for i, t in enumerate(lado_a_lado.trechos, start=1)}
    usuario = json.dumps({
        "pergunta": pergunta,
        "respostas": lado_a_lado.texto,
        "trechos": [f"[{rotulo}] {texto}" for rotulo, texto in fontes.items()],
    }, ensure_ascii=False)
    try:
        bruto = llm(SISTEMA_SINCRONIZADOR, usuario)
    except Exception:
        bruto = None
    if not isinstance(bruto, dict) or not isinstance(bruto.get("evidence_summary"), list):
        return lado_a_lado
    filtrada, ajustes = filtrar_citacoes_literais(bruto, fontes)
    if any(a["motivo"] != "rotulo_corrigido" for a in ajustes):
        return lado_a_lado  # frase sem citação literal: fato que os agentes não trouxeram
    resposta = normalizar_frases_citadas(filtrada)
    verificacao = verificar_citacoes(resposta, len(lado_a_lado.trechos))
    texto = str(resposta.get("evidence_summary") or "").strip()
    if not verificacao.valida or not texto:
        return lado_a_lado
    return Sincronizacao(texto=texto, modo="integrada", trechos=lado_a_lado.trechos)
