"""Limpeza de ênfase e validação/normalização de seções em prepare_rag.py."""

import glob
import importlib.util
import json
from pathlib import Path
import re

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


@pytest.mark.parametrize(
    ("titulo", "esperado"),
    [
        ("RECOMENDA Ç ÃO", "RECOMENDAÇÃO"),
        ("6. RECOMENDA Ç ÃO DE INGESTÃO DE GRUPOS ALIMENTARES", "6. RECOMENDAÇÃO DE INGESTÃO DE GRUPOS ALIMENTARES"),
        ("5. ADEQUA Ç ÃO NUTRICIONAL DA DIETA VEGETARIANA", "5. ADEQUAÇÃO NUTRICIONAL DA DIETA VEGETARIANA"),
        ("2. DEFINI Ç ÕES", "2. DEFINIÇÕES"),
        ("2.2 - O vegetarianismo no Brasil.", "2.2 - O vegetarianismo no Brasil"),
        (
            "7. ANEXO 1 - Grupos Alimentares e suas Medidas Caseiras .",
            "7. ANEXO 1 - Grupos Alimentares e suas Medidas Caseiras",
        ),
        ("s1. agentes anabólicos.", "s1. agentes anabólicos"),
        ("s4. agentes com atividade anti-estrogênica.", "s4. agentes com atividade anti-estrogênica"),
        (
            "Iv. substâncias e métodos proibidos em competição.",
            "Iv. substâncias e métodos proibidos em competição",
        ),
        (
            "Relation Between Sleep and Obesity: A Literature Review.",
            "Relation Between Sleep and Obesity: A Literature Review",
        ),
        ("r e f e r e n c e s", "references"),
    ],
)
def test_normalize_title(titulo, esperado):
    assert prepare_rag.normalize_title(titulo) == esperado


@pytest.mark.parametrize(
    "titulo_invalido",
    [
        "deficiência [121].",
        "Tabela 9: Os mitos da proteína vegetal [110].",
        "Tabela 1: Estudos epidemiológicos",
        "(arnow, Kenardy & agras, 1995)",
        "IIa, Nível de evidência A.",
        "recomendação I, Nível de evidência A.",
        "recomendação I, Nível de evidência C.",
        "Assim, a carne vermelha (190 kcal) é substituída por 3,5 porções de feijão...",
        "acompanhamento individualizado.",
        "idoneidade dos serviços.",
        "2006 ministério da saúde.",
        "sHaPiro, L. Something from the oven . new York: Penguin, 2004.",
        "Aprova o Código de Ética e de Conduta do Nutricionista e dá outras providências .",
        "© 2013 Elsevier Editora Ltda. Todos os direitos reservados.",
    ],
)
def test_is_invalid_heading_identifica_titulos_invalidos(titulo_invalido):
    assert prepare_rag.is_invalid_heading(titulo_invalido) is True


@pytest.mark.parametrize(
    "titulo_valido",
    [
        "5.1 MACRONUTRIENTES",
        "2. DEFINIÇÃO",
        "CAPÍTULO 1. INTRODUÇÃO",
        "escala de alimentação emocional – ees",
        "TRATAMENTO NUTRICIONAL",
    ],
)
def test_is_invalid_heading_aceita_titulos_validos(titulo_valido):
    assert prepare_rag.is_invalid_heading(titulo_valido) is False


def test_clean_page_descarta_titulo_invalido_e_volta_a_secao_valida_da_mesma_pagina():
    raw_markdown = """
### Escala de Avaliação

Texto da primeira seção da página.

### (arnow, Kenardy & agras, 1995)

Texto que deve manter a seção válida anterior da mesma página.
"""
    paragraphs, skipping, final_section = prepare_rag.clean_page(raw_markdown, False, "")
    assert skipping is False
    assert final_section == "Escala de Avaliação"
    assert len(paragraphs) == 2
    assert paragraphs[0][0] == "Escala de Avaliação"
    assert paragraphs[1][0] == "Escala de Avaliação"


def test_clean_page_deixa_secao_vazia_se_titulo_invalido_nao_tem_secao_previa_na_pagina():
    raw_markdown = """
#### deficiência [121].

Texto após o título inválido sem seção prévia nesta página física.
"""
    paragraphs, skipping, final_section = prepare_rag.clean_page(raw_markdown, False, "SecaoDaPaginaAnterior")
    assert skipping is False
    assert final_section == ""
    assert len(paragraphs) == 1
    assert paragraphs[0][0] == ""


def test_todos_os_trechos_cumprem_padrao_de_secao():
    """Conferência no CI: nenhum Trecho no corpus possui seção fora do padrão definido."""
    rag_dir = Path(__file__).resolve().parents[1] / "corpus/nutricao/rag"
    arquivos = sorted(rag_dir.glob("*.jsonl"))
    assert arquivos, "Nenhum arquivo JSONL encontrado em corpus/nutricao/rag"

    erros = []
    total_trechos = 0
    for caminho in arquivos:
        with caminho.open(encoding="utf-8") as f:
            for linha in f:
                trecho = json.loads(linha)
                total_trechos += 1
                secao = trecho.get("secao", "")
                tid = trecho.get("id", "")
                if not secao:
                    continue
                if secao.endswith("."):
                    erros.append(f"{tid}: seção termina com ponto: {secao!r}")
                if re.search(r"\[\d+\]", secao):
                    erros.append(f"{tid}: seção contém referência numérica: {secao!r}")
                if re.search(r"(?<=[A-Za-zÀ-Úà-ú])\s+[çÇ]\s+(?=[A-Za-zÀ-Úà-ú])", secao) or re.search(
                    r"\b[çÇ]\s+ão\b", secao, re.I
                ):
                    erros.append(f"{tid}: seção contém cedilha solta ou letras espaçadas: {secao!r}")
                if re.search(r"\bN[íi]vel de evid[êe]ncia\b", secao, re.I):
                    erros.append(f"{tid}: seção contém nível de evidência: {secao!r}")
                if re.search(r"^\([A-Za-zÀ-Úà-ú]+.*?\d{4}\)$", secao):
                    erros.append(f"{tid}: seção é citação parentética: {secao!r}")
                if re.match(r"^Tabela\s+\d+[:.]", secao, re.I):
                    erros.append(f"{tid}: seção é legenda de tabela: {secao!r}")

    assert not erros, f"Encontradas {len(erros)} seções fora do padrão:\n" + "\n".join(erros[:20])
    assert total_trechos > 0
