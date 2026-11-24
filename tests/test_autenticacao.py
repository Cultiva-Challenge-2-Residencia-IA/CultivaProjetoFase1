"""Autenticação dos endpoints de chat e de exclusão do Histórico (issue #108).

Os Agentes de área são falsos e o serviço de chat é o real, com Histórico num SQLite temporário: o
teste olha quem pode ler e apagar o quê, não a qualidade das respostas.
"""

import json
from typing import List

from fastapi.testclient import TestClient
import pytest

import src.api as api
from src.chat.autenticacao import (
    TokenInvalido,
    _b64,
    _assinatura,
    emitir_token,
    verificar_token,
)
from src.chat.historico import HistoricoSQLite
from src.chat.servico import CHAT_GERAL, ConversaDeOutroUsuario, ServicoDeChat
from src.models.schemas import ConsultantResponse
from src.orquestrador.reescrita import Mensagem
from src.orquestrador.roteamento import AREA_NUTRICAO, AREA_SAUDE_FISICA

SEGREDO = "segredo-de-teste-com-pelo-menos-32-caracteres"
OUTRO_SEGREDO = "outro-segredo-de-teste-com-mais-de-32-caracteres"


class AgenteFalso:
    def __init__(self, area: str):
        self.area = area
        self.historicos: List[List[Mensagem]] = []

    def responder(self, pergunta: str, top_k: int, consultas_extras: List[str],
                  historico: List[Mensagem]) -> ConsultantResponse:
        self.historicos.append(list(historico))
        n = len(self.historicos)
        return ConsultantResponse(
            response_id=f"r-{self.area}-{n}", original_query=pergunta, effective_query=pergunta,
            guardrail_triggered=False, intent_category="SAFE_EVIDENCE_QUERY",
            evidence_summary=f"Resposta de {self.area}.", physiological_mechanism="", protocol_findings="",
            evidence_grade="N/A", corpus_version="c", prompt_version="p", model_version="m", fontes_version="f",
        )


def _cabecalho(usuario_id: str, segredo: str = SEGREDO, **kwargs) -> dict:
    return {"Authorization": f"Bearer {emitir_token(usuario_id, segredo.encode(), **kwargs)}"}


@pytest.fixture
def agentes():
    return {AREA_NUTRICAO: AgenteFalso(AREA_NUTRICAO), AREA_SAUDE_FISICA: AgenteFalso(AREA_SAUDE_FISICA)}


@pytest.fixture
def servico(tmp_path, agentes):
    return ServicoDeChat(agentes=agentes, historico=HistoricoSQLite(tmp_path / "conversas.sqlite3"))


@pytest.fixture
def cliente(monkeypatch, servico):
    monkeypatch.setenv("CULTIVA_AUTH_SEGREDO", SEGREDO)
    monkeypatch.setattr(api, "get_servico_de_chat", lambda: servico)
    monkeypatch.setattr(api, "save_response_trace", lambda resposta: None)
    return TestClient(api.app)


def _enviar(cliente, usuario_id, conversa_id, mensagem, chat="geral"):
    return cliente.post(f"/chat/{chat}", json={"conversa_id": conversa_id, "mensagem": mensagem},
                        headers=_cabecalho(usuario_id))


# Token


def test_token_emitido_volta_com_o_usuario():
    assert verificar_token(emitir_token("u1", SEGREDO.encode()), SEGREDO.encode()) == "u1"


def test_token_com_outro_segredo_e_recusado():
    with pytest.raises(TokenInvalido):
        verificar_token(emitir_token("u1", OUTRO_SEGREDO.encode()), SEGREDO.encode())


def test_token_expirado_e_recusado():
    token = emitir_token("u1", SEGREDO.encode(), validade_s=60, agora=1_000)
    assert verificar_token(token, SEGREDO.encode(), agora=1_059) == "u1"
    with pytest.raises(TokenInvalido, match="expirado"):
        verificar_token(token, SEGREDO.encode(), agora=1_060)


def test_payload_trocado_invalida_a_assinatura():
    """Trocar o `sub` sem o segredo não serve: a assinatura deixa de bater."""
    versao, _payload, assinatura = emitir_token("u1", SEGREDO.encode()).split(".")
    payload = _b64(json.dumps({"sub": "u2", "iat": 0, "exp": 10**12}).encode())
    with pytest.raises(TokenInvalido):
        verificar_token(f"{versao}.{payload}.{assinatura}", SEGREDO.encode())


@pytest.mark.parametrize("token", ["", "abc", "v1.x", "v2.a.b", "v1.a.b.c", "v1.ç.b", "x" * 5000])
def test_token_malformado_e_recusado(token):
    with pytest.raises(TokenInvalido):
        verificar_token(token, SEGREDO.encode())


@pytest.mark.parametrize("dados", [{"exp": 10**12}, {"sub": "", "exp": 10**12}, {"sub": "u1"},
                                   {"sub": "u1", "exp": "nunca"}, {"sub": "u1", "exp": True}, ["u1"]])
def test_payload_assinado_mas_incompleto_e_recusado(dados):
    conteudo = "v1." + _b64(json.dumps(dados).encode())
    with pytest.raises(TokenInvalido):
        verificar_token(f"{conteudo}.{_assinatura(SEGREDO.encode(), conteudo)}", SEGREDO.encode())


# Endpoints: sem token válido, recusa


@pytest.mark.parametrize("metodo,caminho", [
    ("post", "/chat/geral"), ("post", "/chat/nutricao"), ("post", "/chat/saude-fisica"),
    ("delete", "/chat/usuarios/u1"), ("delete", "/chat/usuarios/u1/conversas/c1"),
])
def test_sem_token_os_endpoints_recusam_com_401(cliente, metodo, caminho):
    corpo = {"json": {"usuario_id": "u1", "conversa_id": "c1", "mensagem": "Quais alimentos têm fibra?"}}
    resposta = getattr(cliente, metodo)(caminho, **(corpo if metodo == "post" else {}))
    assert resposta.status_code == 401
    assert resposta.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize("cabecalho", [
    {"Authorization": "Bearer v1.nao.valido"},
    {"Authorization": "Basic dTE6c2VuaGE="},
    _cabecalho("u1", OUTRO_SEGREDO),
    _cabecalho("u1", validade_s=1, agora=1_000),
])
def test_token_invalido_ou_expirado_recusa_com_401(cliente, servico, cabecalho):
    resposta = cliente.post("/chat/geral", json={"conversa_id": "c1", "mensagem": "Quais alimentos têm fibra?"},
                            headers=cabecalho)
    assert resposta.status_code == 401
    assert cliente.delete("/chat/usuarios/u1", headers=cabecalho).status_code == 401
    assert servico.historico.recentes("u1", "c1", limite=10) == []


def test_sem_segredo_e_sem_a_flag_os_endpoints_ficam_fechados(cliente, monkeypatch):
    monkeypatch.setenv("CULTIVA_AUTH_SEGREDO", "")
    resposta = cliente.post("/chat/geral", json={"usuario_id": "u1", "conversa_id": "c1", "mensagem": "Oi"},
                            headers=_cabecalho("u1"))
    assert resposta.status_code == 503
    assert cliente.delete("/chat/usuarios/u1").status_code == 503


def test_segredo_curto_demais_fecha_os_endpoints(cliente, monkeypatch):
    monkeypatch.setenv("CULTIVA_AUTH_SEGREDO", "curto")
    assert cliente.delete("/chat/usuarios/u1", headers=_cabecalho("u1", "curto")).status_code == 503


def test_flag_nao_desliga_a_autenticacao_quando_ha_segredo(cliente, monkeypatch):
    monkeypatch.setenv("CULTIVA_AUTH_DESLIGADA", "true")
    resposta = cliente.post("/chat/geral", json={"usuario_id": "u1", "conversa_id": "c1", "mensagem": "Oi"})
    assert resposta.status_code == 401


def test_modo_de_desenvolvimento_usa_o_usuario_do_corpo(cliente, monkeypatch, servico):
    monkeypatch.setenv("CULTIVA_AUTH_SEGREDO", "")
    monkeypatch.setenv("CULTIVA_AUTH_DESLIGADA", "true")
    corpo = {"usuario_id": "u1", "conversa_id": "c1", "mensagem": "Quais alimentos têm fibra?"}
    assert cliente.post("/chat/geral", json=corpo).status_code == 200
    assert servico.historico.recentes("u1", "c1", limite=10)
    sem_usuario = cliente.post("/chat/geral", json={"conversa_id": "c2", "mensagem": "Oi"})
    assert sem_usuario.status_code == 422


# Endpoints: o Usuário vem do token


def test_usuario_do_token_e_usado_sem_usuario_no_corpo(cliente, servico):
    assert _enviar(cliente, "u1", "c1", "Quais alimentos têm fibra?").status_code == 200
    assert servico.historico.recentes("u1", "c1", limite=10)


def test_usuario_do_corpo_diferente_do_token_recebe_403(cliente, servico):
    resposta = cliente.post("/chat/geral", headers=_cabecalho("u1"),
                            json={"usuario_id": "u2", "conversa_id": "c1", "mensagem": "Quais alimentos têm fibra?"})
    assert resposta.status_code == 403
    assert servico.historico.recentes("u2", "c1", limite=10) == []
    assert servico.historico.recentes("u1", "c1", limite=10) == []


def test_chat_geral_de_a_nao_le_os_chats_de_area_de_b(cliente, agentes):
    assert _enviar(cliente, "usuario-b", "b-nutri", "Tenho hipertensão, quais alimentos têm fibra?",
                   chat="nutricao").status_code == 200
    assert _enviar(cliente, "usuario-a", "a-geral", "Quais alimentos têm ferro?").status_code == 200
    vistos = " ".join(m.texto for m in agentes[AREA_NUTRICAO].historicos[-1])
    assert "hipertensão" not in vistos


def test_conversa_id_de_b_usado_por_a_e_recusado_sem_vazar(cliente, servico, agentes):
    assert _enviar(cliente, "usuario-b", "conversa-1", "Tenho hipertensão, quais alimentos têm fibra?",
                   chat="nutricao").status_code == 200
    resposta = _enviar(cliente, "usuario-a", "conversa-1", "E quais evitar?", chat="nutricao")
    assert resposta.status_code == 403
    assert "hipertensão" not in resposta.text
    assert len(agentes[AREA_NUTRICAO].historicos) == 1  # o agente nem foi chamado para A
    assert servico.historico.recentes("usuario-a", "conversa-1", limite=10) == []
    assert len(servico.historico.recentes("usuario-b", "conversa-1", limite=10)) == 2


def test_mensagem_de_portao_tambem_respeita_a_posse(cliente, servico):
    """Os portões gravam no Histórico; a posse é conferida antes deles."""
    assert _enviar(cliente, "usuario-b", "conversa-1", "Quais alimentos têm fibra?").status_code == 200
    resposta = _enviar(cliente, "usuario-a", "conversa-1", "Senti dor no peito forte correndo")
    assert resposta.status_code == 403
    assert servico.historico.recentes("usuario-a", "conversa-1", limite=10) == []


def test_a_nao_apaga_as_conversas_de_b(cliente, servico):
    assert _enviar(cliente, "usuario-b", "conversa-b", "Quais alimentos têm fibra?").status_code == 200
    cabecalho_a = _cabecalho("usuario-a")
    assert cliente.delete("/chat/usuarios/usuario-b", headers=cabecalho_a).status_code == 403
    assert cliente.delete("/chat/usuarios/usuario-b/conversas/conversa-b", headers=cabecalho_a).status_code == 403
    apagou = cliente.delete("/chat/usuarios/usuario-a/conversas/conversa-b", headers=cabecalho_a)
    assert apagou.status_code == 200 and apagou.json() == {"apagadas": 0}
    assert len(servico.historico.recentes("usuario-b", "conversa-b", limite=10)) == 2


def test_usuario_apaga_a_propria_conversa_e_o_id_fica_livre(cliente, servico):
    assert _enviar(cliente, "u1", "c1", "Quais alimentos têm fibra?").status_code == 200
    apagou = cliente.delete("/chat/usuarios/u1/conversas/c1", headers=_cabecalho("u1"))
    assert apagou.status_code == 200 and apagou.json() == {"apagadas": 2}
    assert servico.historico.recentes("u1", "c1", limite=10) == []
    assert _enviar(cliente, "u2", "c1", "Quais alimentos têm ferro?").status_code == 200


def test_usuario_apaga_todas_as_proprias_conversas(cliente, servico):
    assert _enviar(cliente, "u1", "c1", "Quais alimentos têm fibra?").status_code == 200
    assert _enviar(cliente, "u1", "c2", "Quantos minutos de caminhada por semana?", chat="saude-fisica").status_code == 200
    assert _enviar(cliente, "u2", "c3", "Quais alimentos têm ferro?").status_code == 200
    apagou = cliente.delete("/chat/usuarios/u1", headers=_cabecalho("u1"))
    assert apagou.status_code == 200 and apagou.json() == {"apagadas": 4}
    assert servico.historico.recentes("u1", "c1", limite=10) == []
    assert servico.historico.recentes("u1", "c2", limite=10) == []
    assert len(servico.historico.recentes("u2", "c3", limite=10)) == 2


# Serviço e Histórico


def test_servico_recusa_conversa_de_outro_usuario(servico):
    servico.enviar(CHAT_GERAL, "u1", "c1", "Quais alimentos têm fibra?")
    with pytest.raises(ConversaDeOutroUsuario):
        servico.enviar(CHAT_GERAL, "u2", "c1", "E quais evitar?")


def test_banco_anterior_a_posse_fica_com_o_dono_da_primeira_mensagem(tmp_path):
    import sqlite3

    caminho = tmp_path / "antigo.sqlite3"
    with sqlite3.connect(caminho) as conexao:
        conexao.execute("CREATE TABLE mensagens (id INTEGER PRIMARY KEY AUTOINCREMENT, usuario_id TEXT NOT NULL, "
                        "conversa_id TEXT NOT NULL, chat TEXT NOT NULL, papel TEXT NOT NULL, "
                        "areas TEXT NOT NULL DEFAULT '', texto TEXT NOT NULL, "
                        "criada_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")
        conexao.executemany("INSERT INTO mensagens (usuario_id, conversa_id, chat, papel, texto) VALUES (?, ?, ?, ?, ?)",
                            [("u1", "c1", "geral", "usuario", "a"), ("u2", "c1", "geral", "usuario", "b")])
    conexao.close()
    historico = HistoricoSQLite(caminho)
    assert historico.reservar_conversa("u1", "c1")
    assert not historico.reservar_conversa("u2", "c1")
