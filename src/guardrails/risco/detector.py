"""Detector de sinais de risco (RF-IA03): ideação suicida, autolesão e comportamento alimentar de risco.

Léxico e regras (`lexico.yaml`), locais, determinísticos e sem dependência externa: respondem em
milissegundos (RNF29) e não falham por rede ou modelo. O léxico fica fora do código para ser
revisado sem mexer na lógica.

Camadas semânticas avaliadas e descartadas em 12/11/2026 (eval/risco/README.md): similaridade por
embeddings (alarmes falsos em perguntas comuns, sem ganho de recall) e NLI zero-shot multilíngue.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
import re
from typing import Dict, List, Optional

import yaml

from src.retrieval.hybrid_retriever import normalize_text

LEXICO_PATH = Path(__file__).with_name("lexico.yaml")


@dataclass(frozen=True)
class AvaliacaoRisco:
    risco: bool
    categorias: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class Regra:
    """Expressão regular, com exceção opcional e, se houver o grupo `n`, limites numéricos."""

    padrao: re.Pattern
    excecao: Optional[re.Pattern] = None
    minimo: Optional[float] = None
    maximo: Optional[float] = None

    def aciona(self, texto: str) -> bool:
        if self.excecao and self.excecao.search(texto):
            return False
        for achado in self.padrao.finditer(texto):
            if "n" not in self.padrao.groupindex:
                return True
            numero = float(achado.group("n").replace(",", "."))
            if (self.minimo is None or numero >= self.minimo) and (self.maximo is None or numero <= self.maximo):
                return True
        return False


@lru_cache(maxsize=1)
def carregar_lexico(caminho: Path = LEXICO_PATH) -> Dict[str, List[Regra]]:
    dados = yaml.safe_load(caminho.read_text(encoding="utf-8"))
    lexico: Dict[str, List[Regra]] = {}
    for categoria, regras in dados["categorias"].items():
        compiladas: List[Regra] = []
        for regra in regras:
            if isinstance(regra, str):
                compiladas.append(Regra(re.compile(regra)))
            else:
                excecao = regra.get("excecao")
                compiladas.append(Regra(re.compile(regra["padrao"]), re.compile(excecao) if excecao else None,
                                        regra.get("minimo"), regra.get("maximo")))
        lexico[categoria] = compiladas
    return lexico


def detectar_risco(texto: str) -> AvaliacaoRisco:
    """Retorna as categorias de risco presentes no texto, na ordem do léxico."""
    normalizado = normalize_text(texto)
    categorias = [
        categoria
        for categoria, regras in carregar_lexico().items()
        if any(regra.aciona(normalizado) for regra in regras)
    ]
    return AvaliacaoRisco(risco=bool(categorias), categorias=categorias)
