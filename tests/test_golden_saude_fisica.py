"""Testes do golden set de Saúde Física (Fase 2) e proteção de arquivos existentes."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess

from jsonschema import Draft202012Validator
import pytest

from src.evaluation.golden_saude_fisica.__main__ import main as cli_main
from src.evaluation.golden_saude_fisica.avaliador import (
    avaliar_golden,
    fluidez_linguagem_natural,
)
from src.evaluation.golden_saude_fisica.estatisticas import calcular_estatisticas
from src.evaluation.golden_saude_fisica.validador import (
    GOLDEN_SAUDE_FISICA_DIR,
    SCHEMA_PATH,
    carregar_split,
    serializar_split_deterministico,
    validar_golden,
)

RAIZ = Path(__file__).resolve().parents[1]

CAMINHOS_PROTEGIDOS = (
    "eval/golden/dev/",
    "eval/golden/test/",
    "eval/golden/v2/",
    "eval/golden/resposta/",
    "eval/multiagentes/golden_saude_fisica.json",
    "data/benchmark/eval_questions.json",
    "eval/gates.toml",
    "src/guardrails/risco/lexico.yaml",
    "corpus/manifest.yaml",
    "corpus/nutricao/relatorios/",
    "corpus/nutricao/markdown/",
    "corpus/saudefisica/relatorios/",
    "corpus/saudefisica/markdown/",
)


def test_schema_golden_saude_fisica_valido() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)


def test_validar_golden_dev_e_test_sem_vazamento() -> None:
    res = validar_golden(diretorio=GOLDEN_SAUDE_FISICA_DIR, incluir_test=True)
    assert res.ok, f"Erros de validação: {res.erros}"
    assert not res.avisos, f"Avisos inesperados: {res.avisos}"
    assert res.casos_por_split == {"dev": 36, "test": 36}


def test_estatisticas_cobre_todos_os_tipos_e_equilibrio() -> None:
    stats = calcular_estatisticas(diretorio=GOLDEN_SAUDE_FISICA_DIR, incluir_test=True)
    assert stats["total_casos"] == 72
    esperado_por_split = {
        "adversarial": 4,
        "entre_abas": 4,
        "fora_de_escopo": 4,
        "prescricao": 6,
        "recuperacao": 18,
    }
    assert stats["por_tipo_por_split"]["dev"] == esperado_por_split
    assert stats["por_tipo_por_split"]["test"] == esperado_por_split
    assert not stats["avisos_desequilibrio"]


def test_todos_os_casos_foram_revisados_humanamente() -> None:
    for split in ("dev", "test"):
        dados = carregar_split(split)
        for caso in dados["casos"]:
            assert caso["status_revisao"] == "revisado", caso["id"]
            assert caso["autoria"]["revisao"] == "revisado", caso["id"]
            assert caso["autoria"]["revisor"], caso["id"]


def test_cli_exige_flag_para_ler_holdout(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli_main(["validar"]) == 0
    out_val = capsys.readouterr().out
    assert "'dev': 36" in out_val
    assert "'test'" not in out_val

    assert cli_main(["estatisticas"]) == 0
    stats = json.loads(capsys.readouterr().out)
    assert stats["total_casos"] == 36
    assert list(stats["por_split"]) == ["dev"]


def test_serializacao_deterministica_e_lf() -> None:
    for split in ("dev", "test"):
        caminho = GOLDEN_SAUDE_FISICA_DIR / f"{split}.json"
        bruto = caminho.read_bytes()
        assert b"\r\n" not in bruto, f"{split}.json deve usar LF"
        dados = json.loads(bruto.decode("utf-8"))
        assert serializar_split_deterministico(dados) == bruto.decode("utf-8")


def test_arquivos_protegidos_nao_foram_modificados() -> None:
    proc = subprocess.run(
        ["git", "-c", f"safe.directory={RAIZ.as_posix()}", "diff", "--name-only", "main"],
        cwd=RAIZ,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        pytest.skip(f"git diff indisponível: {proc.stderr.strip()}")
    alterados = [linha.strip() for linha in proc.stdout.splitlines() if linha.strip()]
    violacoes = [
        arq
        for arq in alterados
        if any(arq == prot or arq.startswith(prot) for prot in CAMINHOS_PROTEGIDOS)
    ]
    assert not violacoes, f"Arquivos protegidos modificados: {violacoes}"


def test_avaliador_exige_incluir_test_para_holdout() -> None:
    with pytest.raises(ValueError, match="--incluir-test"):
        avaliar_golden(split="test", incluir_test=False, respostas_por_id={})


def test_avaliador_mede_recuperacao_e_compatibilidade_resposta_ideal() -> None:
    dev_casos = carregar_split("dev")["casos"]
    respostas = {}
    for c in dev_casos:
        evs = (c.get("recuperacao") or {}).get("evidencias", [])
        respostas[c["id"]] = {
            "resposta": c["resposta_referencia"],
            "fontes_recuperadas": [e["source_id"] for e in evs] if evs else [],
            "trechos_recuperados": [e["trecho_id"] for e in evs if e.get("trecho_id")] if evs else [],
            "guardrail_acionado": c["comportamento_esperado"] == "redirecionar_prescricao",
            "abstencao": c["comportamento_esperado"] == "nao_sei",
            "citacoes": [f"[{e['source_id']}]" for e in evs] if evs else [],
            "roteamento_obtido": c.get("roteamento_esperado"),
            "portao_risco_acionado": c["aciona_portao_risco_esperado"],
        }

    rel = avaliar_golden(split="dev", respostas_por_id=respostas)
    m = rel["metricas"]
    assert m["acerto_fonte"]["n"] == 18 and m["acerto_fonte"]["media"] == 1.0
    assert m["acerto_trecho"]["n"] == 18 and m["acerto_trecho"]["media"] == 1.0
    assert m["citacoes_validas"]["n"] == 18 and m["citacoes_validas"]["media"] == 1.0
    assert m["roteamento_ok"]["n"] == 4 and m["roteamento_ok"]["media"] == 1.0
    assert m["portao_risco_ok"]["n"] == 36 and m["portao_risco_ok"]["media"] == 1.0
    assert m["comportamento_ok"]["n"] == 36 and m["comportamento_ok"]["media"] == 1.0
    assert m["f1_referencia"]["media"] == 1.0
    assert m["rouge_l_referencia"]["media"] == 1.0
    assert m["fluidez_pt_br"]["media"] == 1.0
    assert m["cobertura_pontos_obrigatorios"]["media"] == 1.0
    assert m["ausencia_pontos_proibidos"]["media"] == 1.0


def test_avaliador_detecta_citacao_errada_e_ponto_proibido_regex() -> None:
    from src.evaluation.golden_saude_fisica.avaliador import avaliar_caso_resposta

    dev_casos = {c["id"]: c for c in carregar_split("dev")["casos"]}
    rec_errado = avaliar_caso_resposta(
        dev_casos["fis-dev-0001"],
        resposta_texto="Resposta de teste com mais de oitenta caracteres para validar citacao incorreta.",
        citacoes=["[fonte-inexistente]"],
    )
    assert rec_errado["citacoes_validas"] == 0.0

    presc_vazou = avaliar_caso_resposta(
        dev_casos["fis-dev-0019"],
        resposta_texto="Faça 4 series de 12 repeticoes no supino de segunda a sexta.",
        guardrail_acionado=False,
    )
    assert presc_vazou["ausencia_pontos_proibidos"] < 1.0
    assert presc_vazou["comportamento_ok"] == 0.0

    recusa_educada = avaliar_caso_resposta(
        dev_casos["fis-dev-0026"],
        resposta_texto=dev_casos["fis-dev-0026"]["resposta_referencia"],
        guardrail_acionado=True,
    )
    assert recusa_educada["ausencia_pontos_proibidos"] == 1.0
    assert recusa_educada["comportamento_ok"] == 1.0


def test_fluidez_penaliza_copia_crua_em_ingles() -> None:
    copia_ingles = "Adults and older adults should do at least 150 minutes of moderate-intensity aerobic physical activity."
    natural_pt = (
        "Para adultos, as diretrizes da OMS recomendam ao menos 150 minutos semanais de atividade "
        "física moderada para promover saúde e bem-estar."
    )
    assert fluidez_linguagem_natural(natural_pt) > fluidez_linguagem_natural(copia_ingles)

