"""Redação final da resposta (issue #104): tom de conversa, a resposta primeiro, a partir das frases checadas.

Padrão de duas etapas (fundamentar, depois redigir): o Agente de área (ou o Sincronizador) produz as
frases já conferidas pela citação por frase; o redator só as reescreve para a pessoa. O que garante
que ele não acrescenta fato é a checagem, por código:

- toda frase nova aponta frases de origem (`origem`) que existem;
- todo número e toda quantidade com unidade da frase nova estão nas frases de origem
  (`numeros_preservados`, a mesma checagem do PDF da #95);
- os marcadores ([T#], [CONTEXTO], [TACO], [GRAFO]) vêm das frases de origem, nunca do modelo.

Se qualquer frase reprovar, a redação inteira é descartada e fica o texto de antes. A checagem pega
invenção de número e de fonte; uma frase que vai além do sentido da origem (exagero) não é pega, e é
medida à parte (eval/redacao/).
"""

import json
import re
from typing import Any, List, Optional, Sequence

from src.multimodal.pdf import numeros_preservados
from src.retrieval.hybrid_retriever import normalize_text
from src.rag.verificador.citacoes import MARCADOR, dividir_frases

MIN_FRASES, MAX_FRASES = 1, 6

_DADO_PESSOAL = re.compile(
    r"\b(pes[ao]s?|peso|idade|quantos anos|altura|imc|exames?|medicament\w*|remedios?|"
    r"nivel de atividade|quanto voce (treina|come|bebe)|quantas vezes voce|sua rotina|"
    r"objetivo (principal|de peso)|diagnostic\w*)\b")

SISTEMA_REDACAO = """Você é o redator do CULTIVA, um aplicativo educativo de nutrição e atividade física.
Recebe a pergunta da pessoa e frases numeradas, já conferidas com as fontes. Reescreva a resposta para a pessoa
usando SÓ o que está nessas frases.

Guia de voz e tom:
- Comece respondendo diretamente o que foi perguntado; depois, o porquê.
- De 2 a 6 frases curtas, em português do Brasil, tom próximo e simples, sem jargão técnico.
- Fale com a pessoa ("você"), sem julgamento, sem culpa e sem pressão.
- Não acrescente fato, número, alimento, exercício ou recomendação que não esteja nas frases.
- Não dê ordem individual ("você deve", "tome", "coma 30 g"): diga o que as fontes recomendam em geral.
- Se as frases não respondem exatamente a pergunta, diga isso com honestidade e mostre o que elas dizem.
- Em cada frase, informe em "origem" os números das frases que a sustentam.
- Se houver "fatos_da_pessoa" (o que a própria pessoa contou), você pode usar um deles para relacionar a
  resposta à situação dela, na mesma frase de uma informação das frases numeradas: informe em "contexto"
  os ids dos fatos usados. O fato nunca sustenta sozinho uma afirmação. Condição de saúde (como diabetes)
  não serve para ajustar quantidade nem para liberar ou proibir um alimento.

Exemplo
Pergunta: "Pão francês todo dia faz mal?"
Frases: 1. "O Guia recomenda limitar alimentos processados, como pães feitos com farinha, sal e fermento."
2. "O Guia recomenda evitar alimentos ultraprocessados."
Resposta: {"frases": [
  {"frase": "Não precisa cortar, mas vale moderar: o Guia coloca o pão francês entre os alimentos processados, que devem ser limitados.", "origem": [1]},
  {"frase": "O que o Guia pede para evitar de verdade são os ultraprocessados.", "origem": [2]}]}

Responda só com JSON: {"frases": [{"frase": "...", "origem": [1, 2], "contexto": []}]}"""


def encaminhamento(fatos: Sequence[Any]) -> Optional[str]:
    """Frase fixa, por código, quando uma condição de saúde foi entregue (issue #112: a condição só
    orienta a busca e o encaminhamento a profissional)."""
    condicoes = [f.texto for f in fatos if getattr(f, "condicao_de_saude", False)]
    if not condicoes:
        return None
    return (f"Como você contou que {' e que '.join(condicoes)}, vale conversar com um profissional de saúde "
            "sobre o que faz sentido para você.")


def _sem_marcadores(texto: str) -> str:
    return " ".join(MARCADOR.sub(" ", texto).split())


def _marcadores(frases: List[str]) -> str:
    vistos: List[str] = []
    for frase in frases:
        for m in MARCADOR.findall(frase):
            if f"[{m}]" not in vistos:
                vistos.append(f"[{m}]")
    return "".join(vistos)


def redigir(pergunta: str, texto: str, llm, fatos: Sequence[Any] = ()) -> Optional[str]:
    """Texto reescrito, com os marcadores herdados das frases de origem, ou None quando a redação
    falha ou reprova na checagem (aí fica o texto de antes).

    `fatos`: Fatos do Usuário entregues aos agentes (#112). A frase que usa um deles leva [CONTEXTO]
    além dos marcadores da origem; números do fato usado também valem na frase. Com condição de
    saúde usada, a frase não pode ter número. Com condição de saúde entregue, o encaminhamento a
    profissional entra no fim, por código."""
    origem = [f for f in dividir_frases(texto) if _sem_marcadores(f)]
    if not origem or llm is None:
        return None
    numeradas = "\n".join(f"{i}. \"{_sem_marcadores(f)}\"" for i, f in enumerate(origem, 1))
    por_id = {f.id: f for f in fatos}
    entrada = {"pergunta": pergunta, "frases": numeradas}
    if fatos:
        entrada["fatos_da_pessoa"] = [{"id": f.id, "fato": f.texto} for f in fatos]
    try:
        bruto = llm(SISTEMA_REDACAO, json.dumps(entrada, ensure_ascii=False))
    except Exception:
        return None
    itens = bruto.get("frases") if isinstance(bruto, dict) else None
    if not isinstance(itens, list) or not MIN_FRASES <= len(itens) <= MAX_FRASES:
        return None
    saida: List[str] = []
    for item in itens:
        if not isinstance(item, dict):
            return None
        frase = " ".join(str(item.get("frase") or "").split())
        ids = item.get("origem") if isinstance(item.get("origem"), list) else []
        try:
            indices = sorted({int(i) for i in ids})
        except (TypeError, ValueError):
            return None
        if not frase or not indices or any(not 1 <= i <= len(origem) for i in indices):
            return None
        fontes = [origem[i - 1] for i in indices]
        try:
            usados = [por_id[int(i)] for i in (item.get("contexto") or [])]
        except (KeyError, TypeError, ValueError):
            return None  # fato que não foi entregue
        corpo = _sem_marcadores(frase)
        if any(f.condicao_de_saude for f in usados) and re.search(r"\d", corpo):
            return None
        base = " ".join(_sem_marcadores(f) for f in fontes) + " " + " ".join(f.texto for f in usados)
        if not numeros_preservados(corpo, base):
            return None
        marcadores = _marcadores(fontes)
        if not marcadores:
            return None
        if usados and "[CONTEXTO]" not in marcadores:
            marcadores += "[CONTEXTO]"
        final = corpo[-1] if corpo[-1] in ".!?" else "."
        corpo = corpo[:-1].rstrip() if corpo[-1] in ".!?" else corpo
        saida.append(f"{corpo} {marcadores}{final}")
    final_fixo = encaminhamento(fatos)
    if final_fixo:
        saida.append(final_fixo)
    return " ".join(saida)


def esclarecimento_valido(texto: Any) -> Optional[str]:
    """Pergunta de esclarecimento da reescrita: uma pergunta curta, sem número com unidade."""
    from src.agent.guardrails import UNIDADE_DE_QUANTIDADE

    if not isinstance(texto, str):
        return None
    texto = " ".join(texto.split())
    if not texto.endswith("?") or len(texto) > 240 or UNIDADE_DE_QUANTIDADE.search(texto):
        return None
    # Nunca pedir dado pessoal: seria coletar dado para uma prescrição que o CULTIVA não faz (Lei 8.234).
    if _DADO_PESSOAL.search(normalize_text(texto)):
        return None
    return texto

