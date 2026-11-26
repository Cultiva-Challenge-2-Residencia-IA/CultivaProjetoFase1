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
from typing import Any, List, Optional

from src.multimodal.pdf import numeros_preservados
from src.rag.verificador.citacoes import MARCADOR, dividir_frases

MIN_FRASES, MAX_FRASES = 1, 6

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

Exemplo
Pergunta: "Pão francês todo dia faz mal?"
Frases: 1. "O Guia recomenda limitar alimentos processados, como pães feitos com farinha, sal e fermento."
2. "O Guia recomenda evitar alimentos ultraprocessados."
Resposta: {"frases": [
  {"frase": "Não precisa cortar, mas vale moderar: o Guia coloca o pão francês entre os alimentos processados, que devem ser limitados.", "origem": [1]},
  {"frase": "O que o Guia pede para evitar de verdade são os ultraprocessados.", "origem": [2]}]}

Responda só com JSON: {"frases": [{"frase": "...", "origem": [1, 2]}]}"""


def _sem_marcadores(texto: str) -> str:
    return " ".join(MARCADOR.sub(" ", texto).split())


def _marcadores(frases: List[str]) -> str:
    vistos: List[str] = []
    for frase in frases:
        for m in MARCADOR.findall(frase):
            if f"[{m}]" not in vistos:
                vistos.append(f"[{m}]")
    return "".join(vistos)


def redigir(pergunta: str, texto: str, llm) -> Optional[str]:
    """Texto reescrito, com os marcadores herdados das frases de origem, ou None quando a redação
    falha ou reprova na checagem (aí fica o texto de antes)."""
    origem = [f for f in dividir_frases(texto) if _sem_marcadores(f)]
    if not origem or llm is None:
        return None
    numeradas = "\n".join(f"{i}. \"{_sem_marcadores(f)}\"" for i, f in enumerate(origem, 1))
    try:
        bruto = llm(SISTEMA_REDACAO, json.dumps({"pergunta": pergunta, "frases": numeradas}, ensure_ascii=False))
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
        corpo = _sem_marcadores(frase)
        if not numeros_preservados(corpo, " ".join(_sem_marcadores(f) for f in fontes)):
            return None
        marcadores = _marcadores(fontes)
        if not marcadores:
            return None
        final = corpo[-1] if corpo[-1] in ".!?" else "."
        corpo = corpo[:-1].rstrip() if corpo[-1] in ".!?" else corpo
        saida.append(f"{corpo} {marcadores}{final}")
    return " ".join(saida)


def esclarecimento_valido(texto: Any) -> Optional[str]:
    """Pergunta de esclarecimento da reescrita: uma pergunta curta, sem número com unidade."""
    from src.agent.guardrails import UNIDADE_DE_QUANTIDADE

    if not isinstance(texto, str):
        return None
    texto = " ".join(texto.split())
    if not texto.endswith("?") or len(texto) > 240 or UNIDADE_DE_QUANTIDADE.search(texto):
        return None
    return texto

