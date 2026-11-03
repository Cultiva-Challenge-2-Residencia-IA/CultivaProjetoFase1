from fastapi.testclient import TestClient

from api.app import criar_app
from avaliacao.harness import carregar_casos, executar
from modelo import ModeloFalso
from rag.chunking import RAIZ

GOLDEN_DEV = RAIZ / "eval" / "golden" / "dev"


def test_api_saude_e_chat():
    cliente = TestClient(criar_app(ModeloFalso()))
    assert cliente.get("/saude").json()["status"] == "ok"
    r = cliente.post(
        "/abas/nutricao/chat", json={"mensagem": "Por que evitar alimentos ultraprocessados?"}
    )
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["fontes"]
    assert corpo["sinais"]["risco_disparado"] is False


def test_api_rejeita_mensagem_vazia():
    cliente = TestClient(criar_app(ModeloFalso()))
    assert cliente.post("/abas/nutricao/chat", json={"mensagem": ""}).status_code == 422


def test_golden_set_carrega_com_ids_unicos():
    casos = carregar_casos(GOLDEN_DEV)
    assert len(casos) >= 15
    assert {"risco", "fora_de_escopo", "adversarial"} <= {c["tipo"] for c in casos}


def test_harness_com_modelo_falso_aprova_casos_criticos():
    relatorio = executar(ModeloFalso(), GOLDEN_DEV)
    falhas = [(c.id, c.falhas) for c in relatorio.casos if not c.ok]
    assert relatorio.aprovado, falhas
