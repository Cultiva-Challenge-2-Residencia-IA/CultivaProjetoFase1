"""Estatísticas e detecção de desequilíbrios do golden set de Saúde Física."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any, Dict, List

from src.evaluation.golden_saude_fisica.validador import (
    GOLDEN_SAUDE_FISICA_DIR,
    carregar_split,
)


def calcular_estatisticas(
    diretorio: Path = GOLDEN_SAUDE_FISICA_DIR,
    incluir_test: bool = False,
) -> Dict[str, Any]:
    splits = ("dev", "test") if incluir_test else ("dev",)
    por_split: Dict[str, List[Dict[str, Any]]] = {
        s: carregar_split(s, diretorio)["casos"] for s in splits
    }
    todos = [c for casos in por_split.values() for c in casos]

    tipos_total = Counter(c["tipo"] for c in todos)
    temas_total = Counter(c["tema"] for c in todos)
    dificuldades_total = Counter(c["dificuldade"] for c in todos)
    revisao_total = Counter(c["status_revisao"] for c in todos)
    fontes_total = Counter(
        ev["source_id"]
        for c in todos
        if c.get("recuperacao")
        for ev in c["recuperacao"]["evidencias"]
    )
    approval_total = Counter(
        ev["approval_status"]
        for c in todos
        if c.get("recuperacao")
        for ev in c["recuperacao"]["evidencias"]
    )

    avisos: List[str] = []
    total = len(todos)
    if total:
        for tipo, qtd in sorted(tipos_total.items()):
            frac = qtd / total
            if frac < 0.08:
                avisos.append(f"Tipo {tipo!r} sub-representado: {qtd}/{total} ({frac:.1%})")
            elif frac > 0.60:
                avisos.append(f"Tipo {tipo!r} super-representado: {qtd}/{total} ({frac:.1%})")

    if incluir_test and "dev" in por_split and "test" in por_split:
        t_dev = Counter(c["tipo"] for c in por_split["dev"])
        t_test = Counter(c["tipo"] for c in por_split["test"])
        for tipo in sorted(set(t_dev) | set(t_test)):
            if abs(t_dev[tipo] - t_test[tipo]) > 1:
                avisos.append(
                    f"Desequilíbrio entre splits no tipo {tipo!r}: dev={t_dev[tipo]}, test={t_test[tipo]}"
                )

    for fonte, qtd in sorted(fontes_total.items()):
        if qtd > 6:
            avisos.append(f"Fonte {fonte!r} aparece em {qtd} evidências (concentração alta)")

    return {
        "total_casos": total,
        "por_split": {s: len(casos) for s, casos in por_split.items()},
        "por_tipo": dict(sorted(tipos_total.items())),
        "por_tipo_por_split": {
            s: dict(sorted(Counter(c["tipo"] for c in casos).items()))
            for s, casos in por_split.items()
        },
        "por_tema": dict(sorted(temas_total.items())),
        "por_dificuldade": dict(sorted(dificuldades_total.items())),
        "por_status_revisao": dict(sorted(revisao_total.items())),
        "por_fonte": dict(sorted(fontes_total.items())),
        "por_approval_status": dict(sorted(approval_total.items())),
        "avisos_desequilibrio": avisos,
    }
