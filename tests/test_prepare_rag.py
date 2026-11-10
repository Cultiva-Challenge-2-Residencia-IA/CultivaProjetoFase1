"""Limpeza de ênfase em corpus/scripts/prepare_rag.py (issue #36)."""

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "corpus/scripts/prepare_rag.py"
_spec = importlib.util.spec_from_file_location("prepare_rag", SCRIPT)
prepare_rag = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(prepare_rag)


@pytest.mark.parametrize(
    ("markdown", "esperado"),
    [
        # Itálico colado às palavras vizinhas.
        ("Alimentos_in natura_ou minimamente processados", "Alimentos in natura ou minimamente processados"),
        ("alimento<br>_in natura_ou", "alimento in natura ou"),
        ("Lanches do tipo_fast food_| 55,9", "Lanches do tipo fast food | 55,9"),
        ("Grupo Focal,_brainstorm,_exposição", "Grupo Focal, brainstorm, exposição"),
        # Negrito colado a números e palavras.
        ("**Carnes vermelhas**57,68", "Carnes vermelhas 57,68"),
        ("Fatores que**inibem**a absorção", "Fatores que inibem a absorção"),
        ("**1.**Inflamação", "1. Inflamação"),
        # Ênfase comum continua igual.
        ("texto *itálico* e **negrito**", "texto itálico e negrito"),
        ("efeito _p_<0,05", "efeito p<0,05"),
        ("absoluta (_n_= 11)", "absoluta (n= 11)"),
        # Negrito partindo uma sigla não ganha espaço.
        ("**IDAT**E", "IDATE"),
        # Asteriscos escapados (nota) e pares vazios.
        ("p-valor\\*\\*", "p-valor"),
        ("Nozes crua****", "Nozes crua"),
    ],
)
def test_strip_emphasis_nao_cola_palavras(markdown, esperado):
    assert prepare_rag.clean_inline(markdown) == esperado


@pytest.mark.parametrize(
    "texto",
    [
        "http://bvsms.saude.gov.br/bvs/publicacoes/guia_alimentar_populacao_brasileira_2ed.pdf",
        "files/2020-12/Dietary_Guidelines_for_Americans_2020-2025.pdf",
        "002_AF_Nestle_Folheto_Aguas_MaterialCientifico",
        "index.php?option=com_content&task=view",
    ],
)
def test_strip_emphasis_preserva_underscore_de_urls_e_arquivos(texto):
    assert prepare_rag.clean_inline(texto) == texto


def test_url_com_italico_nas_bordas_perde_so_os_marcadores():
    assert prepare_rag.clean_inline("_http://www.nap.edu/openbook.php?record_id=10490_") == (
        "http://www.nap.edu/openbook.php?record_id=10490"
    )
