"""Gates de avaliação da CI: compara o relatório do benchmark com o baseline e os limiares.

Uso:
    python -m src.evaluation.gate --report data/benchmark/baseline_report.json \
        --baseline eval/baselines/benchmark_offline.json --config eval/gates.toml

    # Verificação offline de schemas e gabaritos de respostas (Semana 3):
    python -m src.evaluation.gate --verificar-respostas

    # Avaliação do benchmark comparativo de respostas:
    python -m src.evaluation.gate --report-respostas data/benchmark/relatorio_respostas_comparativo.json

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

    if "overall_metrics" in relatorio and "overall_metrics" in baseline:
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

        if "abstencao" in config:
            resultados.extend(_avaliar_abstencao(relatorio.get("abstention_metrics"), config["abstencao"]))

        # RF-IA03: o mesmo gate no conjunto de desenvolvimento e no holdout, com mínimos próprios.
        for secao, chave in [("risco", "risk_metrics"), ("risco_holdout", "risk_metrics_holdout")]:
            if secao in config:
                resultados.extend(_avaliar_risco(relatorio.get(chave), config[secao], secao))

    if "resumo_condicoes" in relatorio and "respostas" in config:
        resultados.extend(_avaliar_respostas(relatorio["resumo_condicoes"], config["respostas"]))

    return resultados


def _avaliar_abstencao(metricas: Dict[str, Any] | None, minimos: Dict[str, Any]) -> List[Resultado]:
    """RF-IA01: mínimos sobre o bloco `abstention_metrics` do relatório."""
    if not metricas:
        return [Resultado("abstencao", PENDENTE, "relatório sem 'abstention_metrics'")]
    resultados = []
    for metrica, minimo in minimos.items():
        valor = metricas.get(metrica)
        if valor is None:
            resultados.append(Resultado(f"abstencao:{metrica}", FALHOU, "métrica ausente no relatório"))
            continue
        status = PASSOU if float(valor) >= float(minimo) else FALHOU
        resultados.append(Resultado(f"abstencao:{metrica}", status, f"atual={float(valor):.4f} mínimo={float(minimo):.4f}"))
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


def _avaliar_respostas(resumo_condicoes: Dict[str, Any], config_respostas: Dict[str, Any]) -> List[Resultado]:
    """Semana 3: avalia métricas do benchmark comparativo de respostas (LLM x RAG)."""
    resultados: List[Resultado] = []
    condicao_alvo = config_respostas.get("condicao_principal", "rag_atual")
    metricas = resumo_condicoes.get(condicao_alvo)

    if not metricas:
        return [Resultado(f"respostas:{condicao_alvo}", PENDENTE, f"condição '{condicao_alvo}' ausente no relatório")]

    mapeamento = {
        "compliance_legal_minimo": ("compliance_legal_media", "compliance legal (Lei 8.234/1991)"),
        "acuracia_fatos_minima": ("correcao_factual_media", "acurácia factual"),
        "fidelidade_minima": ("fidelidade_contexto_media", "fidelidade ao contexto"),
        "nota_geral_minima": ("nota_geral_media", "nota geral"),
    }

    for chave_cfg, (chave_metrica, rotulo) in mapeamento.items():
        if chave_cfg in config_respostas:
            minimo = float(config_respostas[chave_cfg])
            valor = metricas.get(chave_metrica)
            if valor is None or valor == "N/A":
                resultados.append(Resultado(f"respostas:{chave_metrica}", PENDENTE, f"{rotulo} N/A na condição {condicao_alvo}"))
                continue
            status = PASSOU if float(valor) >= minimo else FALHOU
            resultados.append(
                Resultado(
                    f"respostas:{chave_metrica}",
                    status,
                    f"atual={float(valor):.4f} mínimo={minimo:.4f} ({condicao_alvo}: {rotulo})",
                )
            )
    return resultados


def verificar_integridade_respostas(caminho_dir: Path | None = None) -> List[Resultado]:
    """Verifica schemas e integridade do golden set de respostas (eval/golden/resposta) offline."""
    import jsonschema

    caminho = caminho_dir or Path("eval/golden/resposta")
    schema_path = caminho / "caso_resposta.schema.json"
    dev_path = caminho / "dev.json"
    test_path = caminho / "test.json"

    resultados: List[Resultado] = []

    if not schema_path.is_file():
        return [Resultado("respostas:schema", FALHOU, f"schema não encontrado em {schema_path}")]
    if not dev_path.is_file():
        return [Resultado("respostas:dev", FALHOU, f"dev.json não encontrado em {dev_path}")]
    if not test_path.is_file():
        return [Resultado("respostas:test", FALHOU, f"test.json não encontrado em {test_path}")]

    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator.check_schema(schema)
        validator = jsonschema.Draft202012Validator(schema)
        resultados.append(Resultado("respostas:schema_valido", PASSOU, "caso_resposta.schema.json é válido"))
    except Exception as exc:
        return [Resultado("respostas:schema_valido", FALHOU, f"schema inválido: {exc}")]

    try:
        dev_data = json.loads(dev_path.read_text(encoding="utf-8"))
        dev_cases = dev_data.get("casos", [])
        dev_errors = list(validator.iter_errors(dev_data))
        if dev_errors:
            resultados.append(Resultado("respostas:validacao_dev", FALHOU, f"{len(dev_errors)} erro(s) em dev.json"))
        else:
            resultados.append(Resultado("respostas:validacao_dev", PASSOU, f"dev.json válido ({len(dev_cases)} casos)"))
    except Exception as exc:
        resultados.append(Resultado("respostas:validacao_dev", FALHOU, f"erro ao ler dev.json: {exc}"))
        return resultados

    try:
        test_data = json.loads(test_path.read_text(encoding="utf-8"))
        test_cases = test_data.get("casos", [])
        test_errors = list(validator.iter_errors(test_data))
        if test_errors:
            resultados.append(Resultado("respostas:validacao_test", FALHOU, f"{len(test_errors)} erro(s) em test.json"))
        else:
            resultados.append(Resultado("respostas:validacao_test", PASSOU, f"test.json válido ({len(test_cases)} casos)"))
    except Exception as exc:
        resultados.append(Resultado("respostas:validacao_test", FALHOU, f"erro ao ler test.json: {exc}"))
        return resultados

    # Disjunção estrita de IDs
    dev_ids = {c["id"] for c in dev_cases if isinstance(c, dict) and "id" in c}
    test_ids = {c["id"] for c in test_cases if isinstance(c, dict) and "id" in c}
    intersecao = dev_ids & test_ids
    if intersecao:
        resultados.append(Resultado("respostas:unicidade_ids", FALHOU, f"IDs duplicados entre splits: {intersecao}"))
    else:
        resultados.append(Resultado("respostas:unicidade_ids", PASSOU, "splits dev e test são estritamente disjuntos"))

    # Integridade de fatos atômicos
    total_fatos_dev = sum(len(c.get("fatos_essenciais", [])) for c in dev_cases if isinstance(c, dict))
    total_fatos_test = sum(len(c.get("fatos_essenciais", [])) for c in test_cases if isinstance(c, dict))
    if total_fatos_dev == 0 or total_fatos_test == 0:
        resultados.append(Resultado("respostas:integridade_fatos", FALHOU, "fatos atômicos vazios"))
    else:
        resultados.append(
            Resultado("respostas:integridade_fatos", PASSOU, f"{total_fatos_dev} fatos em dev, {total_fatos_test} fatos em test")
        )

    return resultados


def extrair_baseline(relatorio: Dict[str, Any]) -> Dict[str, Any]:
    """Guarda só o que o gate compara, para o diff do baseline ser legível no PR."""
    baseline = {
        "phase": relatorio.get("phase"),
        "total_questions": relatorio.get("total_questions"),
        "top_k": relatorio.get("top_k"),
        "overall_metrics": relatorio["overall_metrics"],
    }
    for chave in ("risk_metrics", "risk_metrics_holdout", "abstention_metrics"):
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
    parser.add_argument("--report", type=Path, default=None, help="Relatório de busca/recuperação.")
    parser.add_argument("--baseline", type=Path, default=None, help="Baseline de referência.")
    parser.add_argument("--config", type=Path, default=Path("eval/gates.toml"))
    parser.add_argument(
        "--report-respostas",
        type=Path,
        default=None,
        help="Caminho do relatório de benchmark comparativo de respostas (LLM x RAG).",
    )
    parser.add_argument(
        "--verificar-respostas",
        action="store_true",
        help="Executa verificação offline dos schemas e integridade do golden set de respostas.",
    )
    parser.add_argument(
        "--update-baseline",
        action="store_true",
        help="Grava o baseline a partir do relatório em vez de avaliar.",
    )
    args = parser.parse_args(argv)

    if args.update_baseline:
        if not args.report or not args.baseline:
            parser.error("--update-baseline exige --report e --baseline.")
        relatorio = _ler_json(args.report)
        args.baseline.parent.mkdir(parents=True, exist_ok=True)
        args.baseline.write_text(
            json.dumps(extrair_baseline(relatorio), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"Baseline atualizado: {args.baseline}")
        return 0

    if not args.report and not args.verificar_respostas and not args.report_respostas:
        parser.error("Informe --report e --baseline, ou --verificar-respostas, ou --report-respostas.")

    config = tomllib.loads(args.config.read_text(encoding="utf-8")) if args.config.is_file() else {}
    resultados: List[Resultado] = []

    if args.report:
        if not args.baseline:
            parser.error("--report exige --baseline correspondente.")
        relatorio = _ler_json(args.report)
        baseline = _ler_json(args.baseline)
        resultados.extend(avaliar(relatorio, baseline, config))

    if args.report_respostas:
        rel_resp = _ler_json(args.report_respostas)
        if "resumo_condicoes" in rel_resp:
            cfg_resp = config.get("respostas", {})
            resultados.extend(_avaliar_respostas(rel_resp["resumo_condicoes"], cfg_resp))

    if args.verificar_respostas:
        resultados.extend(verificar_integridade_respostas())

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
