"""Seleção de fontes do convert_pdfs.py, inclusive os candidatos original_only em PDF (issue #87)."""

import importlib.util
from pathlib import Path

import pytest
import yaml

RAIZ = Path(__file__).resolve().parents[1]
SCRIPT = RAIZ / "corpus" / "scripts" / "convert_pdfs.py"
FONTES = yaml.safe_load((RAIZ / "corpus" / "manifest.yaml").read_text(encoding="utf-8"))["sources"]


@pytest.fixture(scope="module")
def convert_pdfs():
    pytest.importorskip("pymupdf")  # o script importa o PyMuPDF; ele só existe no ambiente do corpus
    spec = importlib.util.spec_from_file_location("convert_pdfs", SCRIPT)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _ids(fontes):
    return {s["id"] for s in fontes}


def test_sem_opcao_seleciona_so_as_fontes_pdf_do_rag(convert_pdfs):
    escolhidas = convert_pdfs.selecionar_fontes(FONTES)
    assert escolhidas
    assert all(s.get("kind", "pdf") == "pdf" for s in escolhidas)


def test_candidatos_seleciona_os_original_only_em_pdf_com_markdown(convert_pdfs):
    escolhidas = convert_pdfs.selecionar_fontes(FONTES, candidatos=True)
    esperadas = {s["id"] for s in FONTES if s.get("kind") == "original_only" and s.get("markdown_path")
                 and s.get("original_path", "").endswith(".pdf")}
    assert _ids(escolhidas) == esperadas
    assert "who-diretrizes-atividade-fisica-sedentarismo-2020" in esperadas
    assert not _ids(escolhidas) & _ids(convert_pdfs.selecionar_fontes(FONTES))


def test_source_aceita_um_candidato_em_pdf(convert_pdfs):
    escolhidas = convert_pdfs.selecionar_fontes(FONTES, "who-diretrizes-atividade-fisica-sedentarismo-2020")
    assert _ids(escolhidas) == {"who-diretrizes-atividade-fisica-sedentarismo-2020"}


def test_source_recusa_candidato_em_html(convert_pdfs):
    with pytest.raises(ValueError, match="Fonte sem PDF para converter"):
        convert_pdfs.selecionar_fontes(FONTES, "who-physical-activity-factsheet-2024")


def test_source_recusa_resumo_do_pubmed(convert_pdfs):
    fontes = [{"id": "pubmed", "kind": "resumo_pubmed", "raw_path": "x.json"}]
    with pytest.raises(ValueError, match="Fonte sem PDF para converter"):
        convert_pdfs.selecionar_fontes(fontes, "pubmed")


def test_candidato_sem_original_obtido_fica_de_fora(convert_pdfs):
    fonte = {"id": "x", "kind": "original_only", "acquisition_status": "pendente"}
    assert not convert_pdfs.candidato_pdf(fonte)
