"""Contrato entre o corpus e o retriever (ADR 0002)."""

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from src.models.schemas import DocumentChunk
from src.rag.contrato import NIVEL_DE_EVIDENCIA, Retriever, trecho_para_chunk
from src.retrieval.hybrid_retriever import HybridRetriever

RAIZ = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((RAIZ / "corpus/schemas/trecho.schema.json").read_text(encoding="utf-8"))
ARQUIVOS = sorted((RAIZ / "corpus/nutricao/rag").glob("*.jsonl"))


def _trechos():
    for arquivo in ARQUIVOS:
        for linha in arquivo.read_text(encoding="utf-8").splitlines():
            yield arquivo.name, json.loads(linha)


def test_schema_e_valido():
    Draft202012Validator.check_schema(SCHEMA)


def test_ha_trechos_no_corpus():
    assert ARQUIVOS, "nenhum JSONL em corpus/nutricao/rag"


def test_todo_trecho_respeita_o_schema():
    validador = Draft202012Validator(SCHEMA)
    erros = [
        f"{nome}: {trecho['id']}: {erro.message}"
        for nome, trecho in _trechos()
        for erro in validador.iter_errors(trecho)
    ]
    assert not erros, "\n".join(erros[:10])


def test_ids_dos_trechos_sao_unicos():
    ids = [trecho["id"] for _, trecho in _trechos()]
    assert len(ids) == len(set(ids))


def test_tabela_de_evidencia_cobre_os_tipos_do_schema():
    tipos = set(SCHEMA["properties"]["tipo_fonte"]["enum"])
    assert set(NIVEL_DE_EVIDENCIA) == tipos
    niveis_validos = set(DocumentChunk.model_fields["evidence_level"].annotation.__args__)
    assert set(NIVEL_DE_EVIDENCIA.values()) <= niveis_validos


def test_trecho_vira_chunk_preservando_pagina_link_e_status():
    trecho = {
        "id": "fonte-exemplo-p007-02",
        "fonte_id": "fonte-exemplo",
        "titulo_fonte": "Guia de exemplo",
        "instituicoes": ["Instituição A", "Instituição B"],
        "ano": 2020,
        "tipo_fonte": "diretriz",
        "fonte_url": "https://exemplo.org/guia.pdf",
        "doi": None,
        "pagina_pdf": 7,
        "secao": "Regra de ouro",
        "texto": "Prefira alimentos in natura.",
        "licenca": "CC-BY-4.0",
        "approval_status": "aprovado",
    }
    chunk = trecho_para_chunk(trecho)
    assert chunk.chunk_id == trecho["id"] and chunk.doc_id == "fonte-exemplo"
    assert chunk.source_organization == "Instituição A; Instituição B"
    assert chunk.evidence_level == "GUIDELINE_CONSENSUS"
    assert chunk.section_path == "Regra de ouro (pág. 7)"
    assert chunk.pagina_pdf == 7 and chunk.fonte_url == trecho["fonte_url"]
    assert chunk.approval_status == "aprovado" and chunk.licenca == "CC-BY-4.0"
    assert chunk.raw_text == trecho["texto"]
    assert chunk.contextualized_text.endswith("\nPrefira alimentos in natura.")
    assert "Guia de exemplo" in chunk.contextualized_text


def test_secao_vazia_usa_so_a_pagina():
    trecho = next(t for _, t in _trechos())
    trecho = {**trecho, "secao": ""}
    assert trecho_para_chunk(trecho).section_path == f"pág. {trecho['pagina_pdf']}"


@pytest.fixture(scope="module")
def retriever_do_corpus():
    chunks = [trecho_para_chunk(t) for _, t in _trechos()]
    return HybridRetriever(chunks)


def test_retriever_cumpre_a_interface(retriever_do_corpus):
    assert isinstance(retriever_do_corpus, Retriever)


def test_recuperacao_devolve_fonte_pagina_e_respeita_o_limite_por_documento(retriever_do_corpus):
    resultados = retriever_do_corpus.retrieve("Quais são as quatro categorias de alimentos da classificação NOVA?", top_k=4)
    assert 1 <= len(resultados) <= 4
    contagem: dict[str, int] = {}
    for item in resultados:
        assert item.chunk.pagina_pdf and item.chunk.doc_id
        contagem[item.chunk.doc_id] = contagem.get(item.chunk.doc_id, 0) + 1
    assert max(contagem.values()) <= 2
