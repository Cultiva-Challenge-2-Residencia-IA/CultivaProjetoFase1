"""Verificação dos Trechos JSONL contra o manifesto e a origem (issue #22)."""

import copy
import json
from pathlib import Path
import sys

import pytest
import yaml

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "corpus/scripts"))

import verify_trechos  # noqa: E402

MANIFESTO = yaml.safe_load((RAIZ / "corpus/manifest.yaml").read_text(encoding="utf-8"))
GUIA = "guia-alimentar-populacao-brasileira-2014"


@pytest.fixture
def manifesto():
    return copy.deepcopy(MANIFESTO)


def _fonte(manifesto, sid):
    return next(s for s in manifesto["sources"] if s["id"] == sid)


def _geracao_alterada(tmp_path, sid, **campos):
    geracao = json.loads(verify_trechos.GENERATION_PATH.read_text(encoding="utf-8"))
    if campos.get("remover"):
        del geracao["fontes"][sid]
    else:
        geracao["fontes"][sid].update(campos)
    caminho = tmp_path / "geracao.json"
    caminho.write_text(json.dumps(geracao), encoding="utf-8")
    return caminho


def test_trechos_versionados_batem_com_manifesto_e_origem(manifesto):
    assert verify_trechos.problemas_dos_trechos(manifesto) == {}


def test_status_de_aprovacao_desatualizado_e_apontado(manifesto):
    fonte = _fonte(manifesto, GUIA)
    fonte["approval_status"] = "pendente" if fonte["approval_status"] == "aprovado" else "aprovado"
    problemas = verify_trechos.problemas_dos_trechos(manifesto)
    assert list(problemas) == [GUIA]
    assert any(p.startswith("approval_status diverge do manifesto") for p in problemas[GUIA])


def test_licenca_desatualizada_e_apontada(manifesto):
    _fonte(manifesto, GUIA)["license"] = "outra licença"
    problemas = verify_trechos.problemas_dos_trechos(manifesto)
    assert any(p.startswith("licenca diverge do manifesto") for p in problemas[GUIA])


def test_markdown_alterado_depois_da_geracao(manifesto, tmp_path):
    markdown = tmp_path / "guia.md"
    markdown.write_text((RAIZ / _fonte(manifesto, GUIA)["markdown_path"]).read_text(encoding="utf-8") + "\nx\n",
                        encoding="utf-8")
    _fonte(manifesto, GUIA)["markdown_path"] = str(markdown)
    problemas = verify_trechos.problemas_dos_trechos(manifesto)
    assert "Markdown mudou depois da geração dos Trechos" in problemas[GUIA]


def test_pagina_fora_do_pdf(manifesto):
    _fonte(manifesto, GUIA)["pdf_pages"] = 1
    problemas = verify_trechos.problemas_dos_trechos(manifesto)
    assert any("fora de 1..1" in p for p in problemas[GUIA])


def test_jsonl_editado_a_mao(manifesto, tmp_path):
    geracao = _geracao_alterada(tmp_path, GUIA, jsonl_sha256="0" * 64)
    problemas = verify_trechos.problemas_dos_trechos(manifesto, generation_path=geracao)
    assert problemas[GUIA] == ["JSONL editado depois da geração"]


def test_script_ou_config_alterados_depois_da_geracao(manifesto, tmp_path):
    geracao = _geracao_alterada(tmp_path, GUIA, prepare_rag_sha256="0" * 64, rag_config_sha256="0" * 64)
    problemas = verify_trechos.problemas_dos_trechos(manifesto, generation_path=geracao)
    assert problemas[GUIA] == [
        "prepare_rag.py mudou depois da geração dos Trechos",
        "seção da fonte no rag.yaml mudou depois da geração dos Trechos",
    ]


def test_fonte_sem_jsonl_gerado(manifesto, tmp_path):
    geracao = _geracao_alterada(tmp_path, GUIA, remover=True)
    problemas = verify_trechos.problemas_dos_trechos(manifesto, generation_path=geracao)
    assert problemas[GUIA] == ["fonte sem registro em geracao.json (JSONL nunca gerado)"]
    assert any("JSONL sem fonte correspondente" in p for chave, ps in problemas.items() if chave != GUIA
               for p in ps)


def test_mensagem_diz_qual_fonte_regenerar(manifesto):
    _fonte(manifesto, GUIA)["approval_status"] = "outro"
    with pytest.raises(ValueError) as erro:
        verify_trechos.verify(manifesto)
    assert f"prepare_rag.py --source {GUIA}" in str(erro.value)
