"""Avaliação do detector de risco (RF-IA03) no conjunto `eval/risco/casos.json`.

Gera dois blocos do relatório do benchmark, lidos pelo gate de risco (`eval/gates.toml`):

- `risk_metrics`: conjunto de desenvolvimento (`eval/risco/casos.json`), usado para escrever o léxico;
- `risk_metrics_holdout`: casos escritos por quem não escreveu o léxico (`eval/risco/holdout.json`).
  É o que mede a generalização; um recall alto só no desenvolvimento mede cobertura.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from src.config import RISCO_CASOS_PATH, RISCO_HOLDOUT_PATH
from src.guardrails.risco import detectar_risco


def avaliar_risco(caminho: Path = RISCO_CASOS_PATH) -> Dict[str, Any]:
    casos = json.loads(caminho.read_text(encoding="utf-8"))["casos"]
    vp = fp = fn = vn = 0
    falsos_negativos, falsos_positivos = [], []
    por_categoria: Dict[str, Dict[str, int]] = {}
    so_similaridade = 0
    for caso in casos:
        avaliacao = detectar_risco(caso["texto"])
        detectado = avaliacao.risco
        so_similaridade += int(caso["risco"] and avaliacao.camadas == ["similaridade"])
        if caso["risco"]:
            estat = por_categoria.setdefault(caso["categoria"], {"positivos": 0, "detectados": 0})
            estat["positivos"] += 1
            estat["detectados"] += int(detectado)
            if detectado:
                vp += 1
            else:
                fn += 1
                falsos_negativos.append(caso["id"])
        elif detectado:
            fp += 1
            falsos_positivos.append(caso["id"])
        else:
            vn += 1
    return {
        "positives": vp + fn,
        "negatives": fp + vn,
        "recall": round(vp / (vp + fn), 4) if vp + fn else 0.0,
        "precision": round(vp / (vp + fp), 4) if vp + fp else 0.0,
        "true_positives": vp,
        "false_positives": fp,
        "false_negatives": fn,
        "recall_por_categoria": {
            cat: round(e["detectados"] / e["positivos"], 4) for cat, e in sorted(por_categoria.items())
        },
        # Positivos que só a camada de similaridade pegou (o léxico sozinho teria perdido).
        "detectados_so_por_similaridade": so_similaridade,
        "falsos_negativos": falsos_negativos,
        "falsos_positivos": falsos_positivos,
    }


def avaliar_risco_holdout(caminho: Path = RISCO_HOLDOUT_PATH) -> Dict[str, Any]:
    return avaliar_risco(caminho)
