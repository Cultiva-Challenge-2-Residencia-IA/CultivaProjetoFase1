"""Comparação de frameworks de guardrail (issue #52), sem Ollama e sem os frameworks."""

import json

from src.evaluation.comparacao_guardrails import candidatos, casos, config, medir


def test_casos_de_fundamentacao_tem_os_tres_tipos_por_pergunta():
    itens = casos.carregar()
    por_caso = {}
    for i in itens:
        por_caso.setdefault(i["caso"], set()).add(i["tipo"])
    assert all(t == {"fiel", "inventada", "trocada"} for t in por_caso.values())
    for i in itens:
        assert i["sustentada"] is (i["tipo"] == "fiel")
        if i["tipo"] == "inventada":
            assert i["invencao"] in i["resposta"] and i["invencao"] not in " ".join(i["trechos"])
        if i["tipo"] == "trocada":
            import re

            assert i["origem_da_troca"] != i["caso"]
            fonte = re.sub(r"\s+", " ", " ".join(i["trechos"]))
            assert not any(f in fonte for f in re.split(r"(?<=[.!?])\s+", i["resposta"]) if f)


def test_frases_da_resposta_fiel_estao_nos_trechos():
    import re

    for i in casos.carregar():
        if i["tipo"] == "fiel":
            fonte = re.sub(r"\s+", " ", " ".join(i["trechos"]))
            assert " ".join(i["frases"]) == i["resposta"]
            assert all(f in fonte for f in i["frases"])


class _LLMFalso:
    def __init__(self, resposta):
        self.resposta, self.chamadas = resposta, []

    def json(self, sistema, usuario):
        self.chamadas.append((sistema, usuario))
        if isinstance(self.resposta, Exception):
            raise self.resposta
        return self.resposta


def test_chamada_direta_le_o_json_e_registra_erro():
    pos = candidatos.DiretoPos(llm=_LLMFalso({"sustentada": False, "afirmacao_sem_base": "x"}))
    v = pos.verificar("p", ["trecho"], "resposta")
    assert v.sustentada is False and v.erro is None
    assert "[T1] trecho" in pos.llm.chamadas[0][1]
    pre = candidatos.DiretoPre(llm=_LLMFalso(TimeoutError("lento")))
    v = pre.verificar("p", ["trecho"])
    assert v.sustentada is None and "TimeoutError" in v.erro


def test_camadas_locais_sao_o_piso_do_nao_sei(tmp_path, monkeypatch):
    respostas = [
        {"id": "A", "conjunto": "abstencao", "split": "test", "tipo": "nutricao_fora_do_corpus",
         "esperado": "nao_sei", "nao_sei_local": True, "risco": False},
        {"id": "B", "conjunto": "abstencao", "split": "test", "tipo": "nutricao_fora_do_corpus",
         "esperado": "nao_sei", "nao_sei_local": False, "risco": False},
        {"id": "C", "conjunto": "golden_v2", "split": "dev", "tipo": "recuperacao",
         "esperado": "responder", "nao_sei_local": False, "risco": False},
    ]
    monkeypatch.setattr(medir.respostas, "ler", lambda: respostas)
    monkeypatch.setattr(config, "BRUTOS_DIR", tmp_path)
    destino = tmp_path / "abstencao" / "x.jsonl"
    destino.parent.mkdir(parents=True)
    # O candidato "aceitaria" A, mas A já foi recusada pelas camadas locais.
    vereditos = [{"id": "A", "sustentada": True, "segundos": 1, "chamadas": 1},
                 {"id": "B", "sustentada": False, "segundos": 1, "chamadas": 1},
                 {"id": "C", "sustentada": True, "segundos": 1, "chamadas": 1}]
    destino.write_text("\n".join(json.dumps(v) for v in vereditos), encoding="utf-8")
    r = medir.resumo_abstencao("x")
    assert r["nutricao_fora_do_corpus"]["test"]["k"] == 2
    assert r["recusa_indevida"]["golden_v2"]["k"] == 0


def test_wilson_cobre_os_extremos():
    assert medir.wilson(0, 6)[0] == 0.0 and medir.wilson(6, 6)[1] == 1.0
    baixo, alto = medir.wilson(3, 6)
    assert baixo < 0.5 < alto
