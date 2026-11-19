"""Checagem determinística das citações por frase (issue #12, RN04, RNF27).

O LLM recebe os Trechos numerados como [T1]..[Tn] e marca cada frase com os Trechos que a
sustentam; dados do grafo causal levam [GRAFO], e da TACO, [TACO]. Esta checagem confere só a
forma: toda frase citada, todo marcador apontando para algo que foi de fato entregue ao modelo.
A partir do prompt v4 (issue #67), cada frase também traz uma citação literal da fonte;
`filtrar_citacoes_literais` remove as frases cuja citação não existe na fonte citada. Se o Trecho
sustenta a frase continua sendo medido por amostra (eval/fundamentacao/).

Critérios: eval/fundamentacao/criterios.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
import unicodedata
from typing import Any, Dict, List, Tuple

MARCADOR = re.compile(r"\[(T\d+|GRAFO|TACO|\?[^\]]*)\]")
# Marcadores logo depois do ponto final ("frase. [T1]") voltam para antes dele ("frase [T1].").
_MARCADORES_APOS_PONTO = re.compile(r"([.!?])((?:\s*\[(?:T\d+|GRAFO|TACO)\])+)")
_FIM_DE_FRASE = re.compile(r"(?<=[.!?])\s+")
FRASE_SEM_BASE = "Não consta nos trechos recuperados."
CAMPOS_DO_LLM = ("evidence_summary", "physiological_mechanism", "protocol_findings")
MIN_PALAVRAS = 4
MIN_PALAVRAS_CITACAO = 4  # citação literal mínima (critérios da #67)


@dataclass
class VerificacaoCitacoes:
    valida: bool
    frases: int = 0
    frases_sem_citacao: List[str] = field(default_factory=list)
    marcadores_invalidos: List[str] = field(default_factory=list)
    trechos_citados: List[int] = field(default_factory=list)  # números T#, em ordem crescente
    problemas: List[str] = field(default_factory=list)


def eh_trecho(marcador: str) -> bool:
    """[T1], [T2]...: marcador de Trecho. [TACO] também começa com "T", então não basta o prefixo."""
    return marcador[:1] == "T" and marcador[1:].isdigit()


def marcador_de_trecho(indice: int) -> str:
    """Marcador do Trecho na posição `indice` (base 0) da lista recuperada."""
    return f"[T{indice + 1}]"


def _marcador(ref: Any) -> str:
    """2 ou "2" ou "T2" -> "[T2]"; "TACO"/"GRAFO" -> "[TACO]"/"[GRAFO]"; o resto vira um marcador
    inválido que a checagem reprova (ex.: "[?fonte]")."""
    texto = str(ref).strip().upper().strip("[]")
    if texto.isdigit():
        return f"[T{int(texto)}]"
    if eh_trecho(texto) or texto in ("TACO", "GRAFO"):
        return f"[{texto}]"
    return f"[?{texto}]"


def normalizar_frases_citadas(resposta: Dict[str, Any]) -> Dict[str, Any]:
    """Formato estruturado (prompt v3): cada campo do LLM é uma lista de {"frase", "trechos"}.
    Converte em texto com os marcadores no fim de cada frase, para a mesma checagem de sempre.
    Campos já em texto ficam como estão."""
    saida = dict(resposta)
    for campo in CAMPOS_DO_LLM:
        valor = resposta.get(campo)
        if not isinstance(valor, list):
            continue
        frases = []
        for item in valor:
            if isinstance(item, dict):
                frase = str(item.get("frase") or "").strip()
                refs = item.get("trechos") or []
                refs = refs if isinstance(refs, list) else [refs]
            else:
                frase, refs = str(item).strip(), []
            if not frase:
                continue
            if frase == FRASE_SEM_BASE:
                frases.append(frase)
                continue
            marcadores = "".join(_marcador(r) for r in refs)
            corpo = frase[:-1].rstrip() if frase[-1] in ".!?" else frase
            final = frase[-1] if frase[-1] in ".!?" else "."
            frases.append(f"{corpo} {marcadores}{final}" if marcadores else f"{corpo}{final}")
        saida[campo] = " ".join(frases)
    return saida


def _normalizar_para_busca(texto: str) -> str:
    """Caixa, formas Unicode, hifenização, pontuação e espaços não contam na busca da citação."""
    texto = unicodedata.normalize("NFKC", texto).casefold()
    texto = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", texto)
    return " " + " ".join(re.findall(r"\w+", texto)) + " "


def _fontes_da_frase(refs: List[Any]) -> List[str]:
    """Rótulos (T1, TACO, GRAFO) que a frase cita; referências fora do formato são ignoradas."""
    rotulos = [_marcador(r).strip("[]") for r in refs]
    return [r for r in rotulos if eh_trecho(r) or r in ("TACO", "GRAFO")]


def citacao_literal_valida(citacao: str, fontes: List[str]) -> bool:
    """A citação tem ao menos MIN_PALAVRAS_CITACAO palavras e aparece, como sequência contínua de
    palavras, no texto de alguma das fontes citadas."""
    alvo = _normalizar_para_busca(citacao or "")
    if len(alvo.split()) < MIN_PALAVRAS_CITACAO:
        return False
    return any(alvo in _normalizar_para_busca(f) for f in fontes if f)


def filtrar_citacoes_literais(
    resposta: Dict[str, Any], textos: Dict[str, str]
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Prompt v4 (issue #67): mantém só as frases cuja `citacao` existe na fonte que elas citam.

    `textos` mapeia o rótulo da fonte ("T1", "TACO", "GRAFO") para o texto entregue ao modelo. A
    frase fixa FRASE_SEM_BASE dispensa citação. Campo em texto corrido (formato antigo) não tem
    citação verificável e fica vazio. Devolve a resposta filtrada e as frases removidas.
    """
    saida = dict(resposta)
    removidas: List[Dict[str, Any]] = []
    for campo in CAMPOS_DO_LLM:
        valor = resposta.get(campo)
        if not isinstance(valor, list):
            if str(valor or "").strip() not in ("", FRASE_SEM_BASE):
                removidas.append({"campo": campo, "frase": str(valor), "motivo": "sem_formato_estruturado"})
                saida[campo] = []
            continue
        mantidas = []
        for item in valor:
            frase = str(item.get("frase") or "").strip() if isinstance(item, dict) else str(item).strip()
            if frase == FRASE_SEM_BASE:
                mantidas.append(item)
                continue
            refs = item.get("trechos") or [] if isinstance(item, dict) else []
            refs = refs if isinstance(refs, list) else [refs]
            citacao = str(item.get("citacao") or "") if isinstance(item, dict) else ""
            fontes = [textos.get(r, "") for r in _fontes_da_frase(refs)]
            if citacao_literal_valida(citacao, fontes):
                mantidas.append(item)
            else:
                removidas.append({"campo": campo, "frase": frase, "citacao": citacao,
                                  "trechos": refs, "motivo": "citacao_literal_ausente_na_fonte"})
        saida[campo] = mantidas
    return saida, removidas


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
                elif eh_trecho(m):
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
