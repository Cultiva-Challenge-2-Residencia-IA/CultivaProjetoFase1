"""Gates de avaliação da CI: compara o relatório do benchmark com o baseline e os limiares.

Uso:
    python -m src.evaluation.gate --report data/benchmark/baseline_report.json \
        --baseline eval/baselines/benchmark_offline.json --config eval/gates.toml

    # Atualiza o baseline a partir de um relatório (mudança intencional, revisada no PR):
    python -m src.evaluation.gate --report ... --baseline ... --update-baseline

Sai com código 1 se algum gate falhar. Gates sem dados suficientes ficam PENDENTES:
não falham, mas emitem aviso visível na CI. Um gate de risco com `falha_conhecida` (link da
issue) abaixo do mínimo fica CONHECIDA: aviso com o número real, sem falhar o job, para não
esconder regressões de outros gates no vermelho de sempre. Com `piso_conhecido`, cair abaixo
do valor já medido volta a falhar.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

PASSOU, FALHOU, PENDENTE, CONHECIDA = "PASSOU", "FALHOU", "PENDENTE", "CONHECIDA"


@dataclass
class Resultado:
    gate: str
    status: str
    detalhe: str


def avaliar(
    relatorio: Dict[str, Any], baseline: Dict[str, Any], config: Dict[str, Any]
) -> List[Resultado]:
    resultados: List[Resultado] = []
    atual = relatorio["overall_metrics"]
    referencia = baseline["overall_metrics"]

    regressao = config.get("regressao", {})
    tolerancia = float(regressao.get("tolerancia", 0.05))
    for metrica in regressao.get("metricas", []):
        if metrica not in atual or metrica not in referencia:
            resultados.append(
                Resultado(f"regressao:{metrica}", FALHOU, "métrica ausente no relatório ou no baseline")
            )
            continue
        delta = atual[metrica] - referencia[metrica]
        status = PASSOU if delta >= -tolerancia else FALHOU
        resultados.append(
            Resultado(
                f"regressao:{metrica}",
                status,
                f"atual={atual[metrica]:.4f} baseline={referencia[metrica]:.4f} "
                f"delta={delta:+.4f} (tolerância -{tolerancia:.2f})",
            )
        )

    for metrica, minimo in config.get("minimos", {}).items():
        if metrica not in atual:
            resultados.append(Resultado(f"minimo:{metrica}", FALHOU, "métrica ausente no relatório"))
            continue
        status = PASSOU if atual[metrica] >= float(minimo) else FALHOU
        resultados.append(
            Resultado(f"minimo:{metrica}", status, f"atual={atual[metrica]:.4f} mínimo={float(minimo):.4f}")
        )

    # RF-IA03: o mesmo gate no conjunto de desenvolvimento e no holdout, com mínimos próprios.
    for secao, chave in [("risco", "risk_metrics"), ("risco_holdout", "risk_metrics_holdout")]:
        if secao in config:
            resultados.extend(_avaliar_risco(relatorio.get(chave), config[secao], secao))
    return resultados


def _avaliar_risco(metricas: Dict[str, Any] | None, config: Dict[str, Any], nome: str = "risco") -> List[Resultado]:
    """RF-IA03/RF-IA04. Fica pendente até existir um conjunto de risco com casos suficientes."""
    positivos_minimos = int(config.get("positivos_minimos", 0))
    if not metricas:
        return [
            Resultado(
                nome,
                PENDENTE,
                "relatório sem as métricas de risco: falta o detector ou o conjunto de casos",
            )
        ]
    positivos = int(metricas.get("positives", 0))
    if positivos < positivos_minimos:
        return [
            Resultado(
                nome,
                PENDENTE,
                f"{positivos} casos de risco; o gate exige pelo menos {positivos_minimos}",
            )
        ]
    resultados = []
    for metrica, chave, minimo in [
        ("recall", "recall", config.get("recall_minimo")),
        ("precisao", "precision", config.get("precisao_minima")),
    ]:
        if minimo is None:
            continue
        valor = float(metricas.get(chave, 0.0))
        status = PASSOU if valor >= float(minimo) else FALHOU
        detalhe = f"atual={valor:.4f} mínimo={float(minimo):.4f} (n+={positivos})"
        conhecida = config.get("falha_conhecida")
        if status == FALHOU and conhecida and metrica == "recall":
            piso = config.get("piso_conhecido")
            if piso is not None and valor < float(piso):
                detalhe += f"; abaixo do piso já medido {float(piso):.4f} (falha conhecida {conhecida})"
            else:
                status = CONHECIDA
                detalhe += f"; falha conhecida, acompanhada em {conhecida}"
        resultados.append(Resultado(f"{nome}:{metrica}", status, detalhe))
    return resultados


def extrair_baseline(relatorio: Dict[str, Any]) -> Dict[str, Any]:
    """Guarda só o que o gate compara, para o diff do baseline ser legível no PR."""
    baseline = {
        "phase": relatorio.get("phase"),
        "total_questions": relatorio.get("total_questions"),
        "top_k": relatorio.get("top_k"),
        "overall_metrics": relatorio["overall_metrics"],
    }
    for chave in ("risk_metrics", "risk_metrics_holdout"):
        if chave in relatorio:
            baseline[chave] = relatorio[chave]
    return baseline


def _ler_json(caminho: Path) -> Dict[str, Any]:
    return json.loads(caminho.read_text(encoding="utf-8"))


def _anotar(resultado: Resultado) -> None:
    """Anotações do GitHub Actions; fora da CI, só a tabela é impressa."""
    if os.getenv("GITHUB_ACTIONS") != "true":
        return
    if resultado.status == FALHOU:
        print(f"::error title=Gate {resultado.gate}::{resultado.detalhe}")
    elif resultado.status == PENDENTE:
        print(f"::warning title=Gate {resultado.gate} pendente::{resultado.detalhe}")
    elif resultado.status == CONHECIDA:
        print(f"::warning title=Gate {resultado.gate} abaixo do mínimo (falha conhecida)::{resultado.detalhe}")


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=Path("eval/gates.toml"))
    parser.add_argument(
        "--update-baseline",
        action="store_true",
        help="Grava o baseline a partir do relatório em vez de avaliar.",
    )
    args = parser.parse_args(argv)

    relatorio = _ler_json(args.report)
    if args.update_baseline:
        args.baseline.parent.mkdir(parents=True, exist_ok=True)
        args.baseline.write_text(
            json.dumps(extrair_baseline(relatorio), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"Baseline atualizado: {args.baseline}")
        return 0

    config = tomllib.loads(args.config.read_text(encoding="utf-8"))
    resultados = avaliar(relatorio, _ler_json(args.baseline), config)
    for r in resultados:
        print(f"{r.status:8s} {r.gate:40s} {r.detalhe}")
        _anotar(r)
    falhas = [r for r in resultados if r.status == FALHOU]
    conhecidas = [r for r in resultados if r.status == CONHECIDA]
    print(f"\n{len(falhas)} gate(s) falharam de {len(resultados)}.")
    if conhecidas:
        print(f"{len(conhecidas)} abaixo do mínimo com falha conhecida (aviso, não falham o job).")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
