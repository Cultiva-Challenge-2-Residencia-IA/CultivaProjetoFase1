"""Restauração da caixa do texto nativo no Markdown (issue #27, `restore_case_from_native`)."""

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "corpus" / "scripts" / "convert_pdfs.py"


@pytest.fixture(scope="module")
def restaurar_caixa():
    pytest.importorskip("pymupdf")  # o script importa o PyMuPDF; ele só existe no ambiente do corpus
    spec = importlib.util.spec_from_file_location("convert_pdfs", SCRIPT)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo.restaurar_caixa


@pytest.mark.parametrize("markdown, nativo, esperado", [
    ("_PREfIRA SEmPRE AlImENToS_ in natUra", "Prefira sempre alimentos in natura", "_Prefira sempre alimentos_ in natura"),
    ("inclusiva. também se observou", "inclusiva. Também se observou", "inclusiva. Também se observou"),
    ("Brasília — DF", "brasília — DF", "Brasília — DF"),          # nativo defeituoso não rebaixa
    ("MiniStério da SaÚde", "Ministério da SAÚde", "Ministério da SaÚde"),  # caixa irregular do nativo é ignorada
    ("texto sem nada a mudar", "Outro texto completamente diferente", "texto sem nada a mudar"),
])
def test_restaura_so_caixa_regular_sem_rebaixar(restaurar_caixa, markdown, nativo, esperado):
    assert restaurar_caixa(markdown, nativo)[0] == esperado


def test_preserva_marcacao_markdown(restaurar_caixa):
    texto, trocas = restaurar_caixa("**PREfIRA** [link](x) e `cOdigo`", "Prefira link e codigo")
    assert texto.startswith("**Prefira** [link](x)") and trocas >= 1
