"""Checagem determinística das citações por frase (issue #12, RN04, RNF27).

O LLM recebe os Trechos numerados como [T1]..[Tn] e marca cada frase com os Trechos que a
sustentam; dados do grafo causal levam [GRAFO], e da TACO, [TACO]. Esta checagem confere só a
forma: toda frase citada, todo marcador apontando para algo que foi de fato entregue ao modelo.
Se o Trecho citado sustenta a frase é a amostra humana (eval/fundamentacao/).

Critérios: eval/fundamentacao/criterios.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Dict, List

MARCADOR = re.compile(r"\[(T\d+|GRAFO|TACO)\]")
# Marcadores logo depois do ponto final ("frase. [T1]") voltam para antes dele ("frase [T1].").
_MARCADORES_APOS_PONTO = re.compile(r"([.!?])((?:\s*\[(?:T\d+|GRAFO|TACO)\])+)")
_FIM_DE_FRASE = re.compile(r"(?<=[.!?])\s+")
FRASE_SEM_BASE = "Não consta nos trechos recuperados."
CAMPOS_DO_LLM = ("evidence_summary", "physiological_mechanism", "protocol_findings")
MIN_PALAVRAS = 4


@dataclass
class VerificacaoCitacoes:
    valida: bool
    frases: int = 0
    frases_sem_citacao: List[str] = field(default_factory=list)
    marcadores_invalidos: List[str] = field(default_factory=list)
    trechos_citados: List[int] = field(default_factory=list)  # números T#, em ordem crescente
    problemas: List[str] = field(default_factory=list)


def marcador_de_trecho(indice: int) -> str:
    """Marcador do Trecho na posição `indice` (base 0) da lista recuperada."""
    return f"[T{indice + 1}]"


def dividir_frases(texto: str) -> List[str]:
    texto = _MARCADORES_APOS_PONTO.sub(lambda m: f"{m.group(2)}{m.group(1)}", texto.strip())
    return [f.strip() for f in _FIM_DE_FRASE.split(texto) if f.strip()]


def _conta(frase: str) -> bool:
    """Frases curtas (títulos, abreviações cortadas como "et al.") não exigem citação."""
    return len(MARCADOR.sub("", frase).split()) >= MIN_PALAVRAS


def verificar_citacoes(
    campos: Dict[str, str], n_trechos: int, tem_grafo: bool = False, tem_taco: bool = False
) -> VerificacaoCitacoes:
    """Confere as citações do texto escrito pelo LLM (os campos de `CAMPOS_DO_LLM`)."""
    permitidos = {f"T{i}" for i in range(1, n_trechos + 1)}
    if tem_grafo:
        permitidos.add("GRAFO")
    if tem_taco:
        permitidos.add("TACO")

    resultado = VerificacaoCitacoes(valida=False)
    citados = set()
    for nome in CAMPOS_DO_LLM:
        for frase in dividir_frases(str(campos.get(nome) or "")):
            if frase == FRASE_SEM_BASE or not _conta(frase):
                continue
            resultado.frases += 1
            marcadores = MARCADOR.findall(frase)
            if not marcadores:
                resultado.frases_sem_citacao.append(frase)
            for m in marcadores:
                if m not in permitidos:
                    resultado.marcadores_invalidos.append(f"[{m}]")
                elif m.startswith("T"):
                    citados.add(int(m[1:]))
    resultado.trechos_citados = sorted(citados)

    if resultado.frases_sem_citacao:
        resultado.problemas.append(f"frase_sem_citacao:{len(resultado.frases_sem_citacao)}")
    if resultado.marcadores_invalidos:
        resultado.problemas.append(f"marcador_invalido:{','.join(sorted(set(resultado.marcadores_invalidos)))}")
    if n_trechos and not citados:
        resultado.problemas.append("nenhum_trecho_citado")
    if resultado.frases == 0:
        resultado.problemas.append("sem_frases")
    resultado.valida = not resultado.problemas
    return resultado
