"""Detector de sinais de risco (RF-IA03): ideação suicida, autolesão e comportamento alimentar de risco.

Duas camadas, locais e sem chamada externa, para responder dentro do p95 de 3 s (RNF29):

1. Léxico e regras (`lexico.yaml`), nas três categorias.
2. Similaridade por embeddings (o mesmo modelo do banco vetorial) com os exemplos de `exemplos.yaml`,
   só para ideação suicida e autolesão. Pega paráfrases que o léxico não conhece. Comportamento
   alimentar fica fora porque, com o modelo atual, essas frases se parecem com perguntas comuns
   de nutrição.

Basta uma camada acionar. O léxico e os exemplos ficam fora do código para revisão independente.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
import re
from typing import Dict, List, Optional, Tuple

import numpy as np
import yaml

from src.config import EMBEDDING_MODEL_NAME, RISCO_LIMIAR_SIMILARIDADE
from src.retrieval.hybrid_retriever import normalize_text

LEXICO_PATH = Path(__file__).with_name("lexico.yaml")
EXEMPLOS_PATH = Path(__file__).with_name("exemplos.yaml")

Regra = Tuple[re.Pattern, Optional[re.Pattern]]


@dataclass(frozen=True)
class AvaliacaoRisco:
    risco: bool
    categorias: List[str] = field(default_factory=list)
    # "lexico" e/ou "similaridade": qual camada acionou (rastreabilidade e avaliação).
    camadas: List[str] = field(default_factory=list)


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


def _normalizar_linhas(matriz: np.ndarray) -> np.ndarray:
    return matriz / np.linalg.norm(matriz, axis=1, keepdims=True)


@lru_cache(maxsize=1)
def _expressoes_idiomaticas(caminho: Path = EXEMPLOS_PATH) -> Tuple[re.Pattern, ...]:
    dados = yaml.safe_load(caminho.read_text(encoding="utf-8"))
    return tuple(re.compile(p) for p in dados.get("expressoes_idiomaticas", []))


@lru_cache(maxsize=1)
def _exemplos_embutidos(caminho: Path = EXEMPLOS_PATH) -> Tuple[np.ndarray, Tuple[str, ...]]:
    from src.retrieval.vector_store import _get_fastembed_model

    dados = yaml.safe_load(caminho.read_text(encoding="utf-8"))["categorias"]
    textos = [t for exemplos in dados.values() for t in exemplos]
    rotulos = tuple(c for c, exemplos in dados.items() for _ in exemplos)
    modelo = _get_fastembed_model(EMBEDDING_MODEL_NAME)
    return _normalizar_linhas(np.array(list(modelo.embed(textos)))), rotulos


def similaridade_com_exemplos(texto: str) -> Tuple[float, str]:
    """Maior cosseno entre o texto e os exemplos de risco, com a categoria do exemplo."""
    from src.retrieval.vector_store import _get_fastembed_model

    exemplos, rotulos = _exemplos_embutidos()
    consulta = _normalizar_linhas(np.array(list(_get_fastembed_model(EMBEDDING_MODEL_NAME).embed([texto]))))
    similaridades = exemplos @ consulta[0]
    indice = int(np.argmax(similaridades))
    return float(similaridades[indice]), rotulos[indice]


def detectar_risco(texto: str, usar_similaridade: bool = True,
                   limiar: float = RISCO_LIMIAR_SIMILARIDADE) -> AvaliacaoRisco:
    """Retorna as categorias de risco presentes no texto e as camadas que acionaram."""
    normalizado = normalize_text(texto)
    categorias = [
        categoria
        for categoria, regras in carregar_lexico().items()
        if any(padrao.search(normalizado) and not (excecao and excecao.search(normalizado))
               for padrao, excecao in regras)
    ]
    camadas = ["lexico"] if categorias else []
    idiomatica = any(p.search(normalizado) for p in _expressoes_idiomaticas())
    if usar_similaridade and not idiomatica:
        similaridade, categoria = similaridade_com_exemplos(texto)
        if similaridade >= limiar:
            camadas.append("similaridade")
            if categoria not in categorias:
                categorias.append(categoria)
    return AvaliacaoRisco(risco=bool(categorias), categorias=categorias, camadas=camadas)
