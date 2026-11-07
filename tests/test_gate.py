import json

from src.evaluation.gate import FALHOU, PASSOU, PENDENTE, avaliar, main

CONFIG = {
    "regressao": {"tolerancia": 0.05, "metricas": ["mean_doc_recall_at_k", "legal_guardrail_accuracy"]},
    "minimos": {"legal_guardrail_accuracy": 1.0},
    "risco": {"recall_minimo": 0.95, "precisao_minima": 0.60, "positivos_minimos": 50},
}
BASELINE = {"overall_metrics": {"mean_doc_recall_at_k": 0.90, "legal_guardrail_accuracy": 1.0}}


def _relatorio(recall=0.90, guardrail=1.0, risco=None):
    rel = {"overall_metrics": {"mean_doc_recall_at_k": recall, "legal_guardrail_accuracy": guardrail}}
    if risco is not None:
        rel["risk_metrics"] = risco
    return rel


def _status(resultados):
    return {r.gate: r.status for r in resultados}


def test_queda_dentro_da_tolerancia_passa():
    status = _status(avaliar(_relatorio(recall=0.86), BASELINE, CONFIG))
    assert status["regressao:mean_doc_recall_at_k"] == PASSOU


def test_queda_acima_de_5pp_falha():
    status = _status(avaliar(_relatorio(recall=0.84), BASELINE, CONFIG))
    assert status["regressao:mean_doc_recall_at_k"] == FALHOU


def test_guardrail_abaixo_do_minimo_falha_mesmo_dentro_da_tolerancia():
    status = _status(avaliar(_relatorio(guardrail=0.96), BASELINE, CONFIG))
    assert status["regressao:legal_guardrail_accuracy"] == PASSOU
    assert status["minimo:legal_guardrail_accuracy"] == FALHOU


def test_metrica_ausente_falha():
    status = _status(avaliar({"overall_metrics": {}}, BASELINE, CONFIG))
    assert status["regressao:mean_doc_recall_at_k"] == FALHOU


def test_risco_sem_metricas_fica_pendente():
    status = _status(avaliar(_relatorio(), BASELINE, CONFIG))
    assert status["risco"] == PENDENTE


def test_risco_com_poucos_casos_fica_pendente():
    risco = {"recall": 0.5, "precision": 0.5, "positives": 10}
    status = _status(avaliar(_relatorio(risco=risco), BASELINE, CONFIG))
    assert status["risco"] == PENDENTE


def test_risco_com_casos_suficientes_e_aplicado():
    risco = {"recall": 0.94, "precision": 0.70, "positives": 60}
    status = _status(avaliar(_relatorio(risco=risco), BASELINE, CONFIG))
    assert status["risco:recall"] == FALHOU
    assert status["risco:precisao"] == PASSOU


def test_main_retorna_1_em_falha_e_0_com_pendencia(tmp_path):
    config = tmp_path / "gates.toml"
    config.write_text(
        '[regressao]\ntolerancia = 0.05\nmetricas = ["mean_doc_recall_at_k"]\n'
        "[risco]\nrecall_minimo = 0.95\nprecisao_minima = 0.6\npositivos_minimos = 50\n",
        encoding="utf-8",
    )
    baseline = tmp_path / "baseline.json"
    baseline.write_text(json.dumps(BASELINE), encoding="utf-8")
    ok, ruim = tmp_path / "ok.json", tmp_path / "ruim.json"
    ok.write_text(json.dumps(_relatorio()), encoding="utf-8")
    ruim.write_text(json.dumps(_relatorio(recall=0.5)), encoding="utf-8")

    args = ["--baseline", str(baseline), "--config", str(config)]
    assert main(["--report", str(ok), *args]) == 0
    assert main(["--report", str(ruim), *args]) == 1


def test_update_baseline_grava_so_metricas(tmp_path):
    relatorio = tmp_path / "rel.json"
    relatorio.write_text(json.dumps({**_relatorio(), "question_results": [1, 2]}), encoding="utf-8")
    destino = tmp_path / "sub" / "baseline.json"
    assert main(["--report", str(relatorio), "--baseline", str(destino), "--update-baseline"]) == 0
    gravado = json.loads(destino.read_text(encoding="utf-8"))
    assert "question_results" not in gravado
    assert gravado["overall_metrics"]["mean_doc_recall_at_k"] == 0.90
