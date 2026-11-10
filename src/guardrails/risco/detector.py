"""Detector de sinais de risco (RF-IA03): ideação suicida, autolesão e comportamento alimentar de risco.

Determinístico e sem chamada externa, para responder dentro do p95 de 3 s (RNF29). O léxico
fica em `lexico.yaml`, separado do código, para ser revisado sem mexer na lógica.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
import re
from typing import Dict, List, Optional, Tuple

import yaml

from src.retrieval.hybrid_retriever import normalize_text

LEXICO_PATH = Path(__file__).with_name("lexico.yaml")

Regra = Tuple[re.Pattern, Optional[re.Pattern]]


@dataclass(frozen=True)
class AvaliacaoRisco:
    risco: bool
    categorias: List[str] = field(default_factory=list)


@lru_cache(maxsize=1)
def carregar_lexico(caminho: Path = LEXICO_PATH) -> Dict[str, List[Regra]]:
    dados = yaml.safe_load(caminho.read_text(encoding="utf-8"))
    lexico: Dict[str, List[Regra]] = {}
    for categoria, regras in dados["categorias"].items():
        compiladas: List[Regra] = []
        for regra in regras:
            if isinstance(regra, str):
                compiladas.append((re.compile(regra), None))
            else:
                excecao = regra.get("excecao")
                compiladas.append((re.compile(regra["padrao"]), re.compile(excecao) if excecao else None))
        lexico[categoria] = compiladas
    return lexico


def detectar_risco(texto: str) -> AvaliacaoRisco:
    """Retorna as categorias de risco presentes no texto, na ordem do léxico."""
    normalizado = normalize_text(texto)
    categorias = [
        categoria
        for categoria, regras in carregar_lexico().items()
        if any(padrao.search(normalizado) and not (excecao and excecao.search(normalizado))
               for padrao, excecao in regras)
    ]
    return AvaliacaoRisco(risco=bool(categorias), categorias=categorias)
