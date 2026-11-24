"""Avaliação offline da checagem de exagero (issue #86), sem Ollama."""

import json

import httpx

from src.evaluation import exagero


def _cliente(conteudo=None, status=200):
    def responder(request):
        if conteudo is None:
            return httpx.Response(status)
        return httpx.Response(status, json={"message": {"content": json.dumps(conteudo)}})
    return httpx.Client(transport=httpx.MockTransport(responder))


def test_frases_julgadas_carregam_com_os_splits_dos_criterios():
    frases = exagero.carregar("todos")
    assert len(frases) == 120
    contagem = {(s, j): sum(f["split"] == s and f["julgamento"] == j for f in frases)
                for s in ("dev", "test") for j in ("sustentada", "parcial")}
    assert contagem == {("dev", "sustentada"): 73, ("dev", "parcial"): 14,
                        ("test", "sustentada"): 28, ("test", "parcial"): 5}
    assert all(f["trechos"] for f in frases)


def test_resumo_conta_achadas_remocao_indevida_e_taxa_projetada():
    linhas = (
        [{"julgamento": "sustentada", "veredito": True, "segundos": 1.0}] * 8
        + [{"julgamento": "sustentada", "veredito": False, "segundos": 1.0}]
        + [{"julgamento": "sustentada", "veredito": None, "segundos": 1.0}]
        + [{"julgamento": "parcial", "veredito": False, "segundos": 1.0}]
        + [{"julgamento": "parcial", "veredito": True, "segundos": 1.0}]
    )
    resumo = exagero.resumir(linhas)
    assert resumo["parciais_achadas"] == 1 and resumo["taxa_parciais_achadas"] == 0.5
    assert resumo["remocao_indevida"] == 1 and resumo["taxa_remocao_indevida"] == 0.1
    assert resumo["falhas"] == 1
    assert resumo["taxa_projetada"] == round(9 / 10, 3)  # a frase sem veredito fica


def test_verificador_le_o_veredito_e_as_ressalvas_perdidas():
    cliente = _cliente({"sustentada": False, "ressalvas_perdidas": ["dose de 75 mg"]})
    v = exagero.VerificadorExagero(cliente=cliente).verificar("A vitamina C aumenta a absorção [T2].", ["..."])
    assert v.sustentada is False and v.problema == "dose de 75 mg" and v.erro is None


def test_falha_do_ollama_ou_json_invalido_mantem_a_frase():
    for cliente in (_cliente(status=500), _cliente({"sustentada": "talvez"})):
        v = exagero.VerificadorExagero(cliente=cliente).verificar("Frase [T1].", ["trecho"])
        assert v.sustentada is None and v.erro


def test_marcadores_saem_da_frase_enviada():
    assert exagero.sem_marcadores("Feijão tem ferro [T1] [TACO].") == "Feijão tem ferro."


def test_limiar_do_nli_e_o_maior_com_remocao_indevida_ate_10_por_cento():
    pontuadas = ([{"julgamento": "sustentada", "pontuacao": p} for p in (0.1, 0.5, 0.6, 0.7, 0.8, 0.9, 0.9, 0.9, 0.9, 0.9)]
                 + [{"julgamento": "parcial", "pontuacao": p} for p in (0.05, 0.55)])
    limiar = exagero.escolher_limiar(pontuadas)
    assert limiar == 0.5  # remove só a sustentada de 0,1 (10%); 0,55 já removeria duas
