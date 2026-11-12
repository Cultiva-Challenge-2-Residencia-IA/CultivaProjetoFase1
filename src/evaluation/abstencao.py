"""Avaliação do "não sei" (RF-IA01, issue #6) no conjunto `eval/abstencao/casos.json`.

Gera o bloco `abstention_metrics` do relatório do benchmark, lido pelo gate `[abstencao]`:

- `nao_sei_fora_de_nutricao`: perguntas fora do domínio que recebem "não sei";
- `respostas_esperadas`: perguntas que o sistema deve responder e responde (recusa indevida = 1 - isso);
- `nao_sei_nutricao_fora_do_corpus`: temas de Nutrição sem Trecho no corpus. Informativo: nenhum
  sinal local separa esse caso (ver eval/abstencao/README.md e a issue #52).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from src.config import ABSTENCAO_CASOS_PATH, ABSTENCAO_LIMIAR_COSSENO


def _taxa(valores: List[bool]) -> float | None:
    return round(sum(valores) / len(valores), 4) if valores else None


def avaliar_abstencao(consultor: Any, caminho: Path = ABSTENCAO_CASOS_PATH) -> Dict[str, Any]:
    casos = json.loads(caminho.read_text(encoding="utf-8"))["casos"]
    resultados = []
    for caso in casos:
        resposta = consultor.consult(caso["pergunta"])
        resultados.append({**caso, "abstencao": resposta.abstencao, "similaridade": resposta.similaridade_maxima})

    def grupo(filtro, split=None):
        return [r for r in resultados if filtro(r) and (split is None or r["split"] == split)]

    def metricas(split=None) -> Dict[str, Any]:
        return {
            "nao_sei_fora_de_nutricao": _taxa([r["abstencao"] for r in grupo(lambda r: r["tipo"] == "fora_de_nutricao", split)]),
            "nao_sei_nutricao_fora_do_corpus": _taxa(
                [r["abstencao"] for r in grupo(lambda r: r["tipo"] == "nutricao_fora_do_corpus", split)]),
            "respostas_esperadas": _taxa([not r["abstencao"] for r in grupo(lambda r: r["esperado"] == "responder", split)]),
        }

    return {
        "limiar_cosseno": ABSTENCAO_LIMIAR_COSSENO,
        "casos": len(resultados),
        **metricas(),
        "por_split": {split: metricas(split) for split in ("dev", "test")},
        "recusas_indevidas": [r["id"] for r in resultados if r["esperado"] == "responder" and r["abstencao"]],
        "fora_de_nutricao_respondidos": [r["id"] for r in resultados if r["tipo"] == "fora_de_nutricao" and not r["abstencao"]],
    }
