import os

from chat.sessao import SessaoChat
from config import carregar_env
from guardrails import mensagens
from modelo import ModeloFalso
from orquestracao import Cultiva


def nova_sessao():
    return SessaoChat(Cultiva(ModeloFalso()))


def test_chat_responde_e_mostra_sinais_so_no_comando():
    sessao = nova_sessao()
    resposta = sessao.processar("Por que evitar alimentos ultraprocessados?")
    assert "Fontes:" in resposta
    assert "trechos recuperados" not in resposta
    sinais = sessao.processar("/sinais")
    assert "trechos recuperados: guia-2014-" in sinais
    assert "risco: não" in sinais


def test_chat_sinais_antes_de_qualquer_resposta():
    assert "Ainda não há resposta" in nova_sessao().processar("/sinais")


def test_chat_risco_mostra_acolhimento_e_categoria():
    sessao = nova_sessao()
    assert sessao.processar("Não aguento mais") == mensagens.ACOLHIMENTO_RISCO
    assert "risco: sim (ideacao_suicida)" in sessao.processar("/sinais")


def test_chat_comandos_de_controle():
    sessao = nova_sessao()
    assert sessao.processar("/sair") is None
    assert sessao.processar("   ") == ""
    assert "/sinais" in sessao.processar("/ajuda")
    assert "Comando desconhecido" in sessao.processar("/xpto")


def test_carregar_env_nao_sobrescreve_variavel_existente(tmp_path, monkeypatch):
    arquivo = tmp_path / ".env"
    arquivo.write_text(
        "# comentário\nCULTIVA_TESTE_A=do_arquivo\nCULTIVA_TESTE_B='com aspas'\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("CULTIVA_TESTE_A", "do_ambiente")
    monkeypatch.delenv("CULTIVA_TESTE_B", raising=False)
    carregar_env(arquivo)
    assert os.environ["CULTIVA_TESTE_A"] == "do_ambiente"
    assert os.environ["CULTIVA_TESTE_B"] == "com aspas"
    monkeypatch.delenv("CULTIVA_TESTE_B")
