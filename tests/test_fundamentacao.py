"""Amostra humana de fundamentação (issue #12): sorteio, cálculo e intervalo, sem LLM."""

import csv

import pytest

from src.evaluation.fundamentacao import calcular, frases_elegiveis, sortear, wilson


def _item(caso, valida=True, resumo="O Guia recomenda evitar ultraprocessados [T1]. Fibras formam gel no intestino [T2]."):
    return {
        "id": caso, "split": "dev", "pergunta": "p", "citacoes_validas": valida,
        "texto_llm": {"evidence_summary": resumo, "physiological_mechanism": "Não consta nos trechos recuperados.",
                      "protocol_findings": "Segundo o grafo, aveia tem beta-glucana [GRAFO]."},
        "trechos": [{"marcador": "T1", "fonte": "Guia", "pagina_pdf": 3, "texto": "evite ultraprocessados"},
                    {"marcador": "T2", "fonte": "Fibras", "pagina_pdf": 7, "texto": "a fibra forma gel"}],
    }


def test_elegiveis_so_de_respostas_validas_e_com_trecho_citado():
    frases = frases_elegiveis([_item("A"), _item("B", valida=False)])
    assert [f["caso"] for f in frases] == ["A", "A"]  # a frase só com [GRAFO] e a frase fixa ficam de fora
    assert frases[1]["trechos_citados"][0]["texto"] == "a fibra forma gel"


def test_sorteio_e_reprodutivel_e_limita_frases_por_resposta():
    frases = [{"caso": f"C{i // 5}", "frase": f"f{i}"} for i in range(50)]  # 10 respostas, 5 frases cada
    a, b = sortear(frases, n=60), sortear(frases, n=60)
    assert a == b
    assert len(a) == 30  # no máximo 3 por resposta
    assert max(sum(f["caso"] == c for f in a) for c in {f["caso"] for f in a}) == 3


def test_wilson():
    assert wilson(57, 60) == pytest.approx([0.8628, 0.9829], abs=1e-3)
    assert wilson(0, 0) == [0.0, 0.0]


def _planilha(tmp_path, julgamentos):
    caminho = tmp_path / "amostra.csv"
    with caminho.open("w", encoding="utf-8", newline="") as arq:
        w = csv.writer(arq)
        w.writerow(["id", "pergunta", "frase", "trechos_citados", "julgamento", "comentario"])
        for i, j in enumerate(julgamentos):
            w.writerow([f"F{i}", "p", "f", "t", j, ""])
    return caminho


def test_calcular_conta_parcial_como_nao_sustentada(tmp_path):
    r = calcular(_planilha(tmp_path, ["sustentada"] * 18 + ["parcial", ""]))
    assert r["frases_julgadas"] == 19 and r["fidelidade"] == pytest.approx(18 / 19, abs=1e-4)
    assert r["atinge_meta"] is False


def test_calcular_recusa_julgamento_fora_da_rubrica(tmp_path):
    with pytest.raises(SystemExit):
        calcular(_planilha(tmp_path, ["sim"]))
