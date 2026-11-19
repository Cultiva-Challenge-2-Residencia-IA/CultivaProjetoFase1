"""Contagens da ablação do seed_guidelines (issue #5), sem construir índice."""

from src.evaluation.ablacao_seed import SEED_PATH, carregar_seed, presenca_seed, regua_antiga


def test_presenca_conta_so_o_top_k():
    listas = [["DOC_A_C01", "guia", "x", "y", "DOC_B_C01"], ["guia", "x", "y", "z"]]
    p = presenca_seed(listas, k=4)
    assert p == {"posicoes_top_k": 8, "posicoes_seed": 1, "fracao_seed": 0.125,
                 "consultas_com_seed": 1, "consultas": 2}


def test_regua_antiga_so_olha_perguntas_que_esperam_seed():
    perguntas = [
        {"id": "Q1", "expected_doc_ids": ["GUIA_MS_INTRO", "DOC_A"]},
        {"id": "Q2", "expected_doc_ids": ["DOC_B", "DOC_C"]},
        {"id": "Q3", "expected_doc_ids": ["GUIA_MS_INTRO"]},
    ]
    relatorio = {"question_results": [
        {"id": "Q1", "retrieved_doc_ids": ["guia", "DOC_A"]},
        {"id": "Q2", "retrieved_doc_ids": ["guia", "x", "y", "z", "DOC_B"]},  # DOC_B fora do top-4
        {"id": "Q3", "retrieved_doc_ids": ["guia"]},
    ]}
    r = regua_antiga(perguntas, relatorio, k=4)
    assert r["perguntas_que_esperam_seed"] == 2
    assert r["com_seed_esperado_no_top_k"] == 1
    assert r["por_pergunta"]["Q2"]["achados_no_top_k"] == []


def test_seed_tem_dez_documentos_com_prefixo_doc():
    assert SEED_PATH.exists()
    docs = {c.doc_id for c in carregar_seed()}
    assert len(docs) == 10
    assert all(d.startswith("DOC_") for d in docs)
