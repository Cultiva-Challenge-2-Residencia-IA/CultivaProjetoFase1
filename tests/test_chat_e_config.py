import pytest

from chat.sessao import SessaoChat
from config import VARIAVEIS_POR_PROVEDOR, ConfiguracaoInvalida, carregar_configuracao
from guardrails import mensagens
from modelo import ModeloFalso, ModeloOllama, criar_modelo
from orquestracao import Cultiva

VARIAVEIS = ("CULTIVA_PROVEDOR", *{v for vs in VARIAVEIS_POR_PROVEDOR.values() for v in vs})


def nova_sessao():
    return SessaoChat(Cultiva(ModeloFalso()))


# ---------------------------------------------------------------- chat


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


def test_chat_perfil_mostra_e_altera_o_que_o_agente_recebe():
    sessao = nova_sessao()
    assert "restricoes_alimentares: vegetariana" in sessao.processar("/perfil")
    saida = sessao.processar("/perfil restricoes vegana, sem lactose")
    assert "restricoes_alimentares: vegana, sem lactose" in saida
    assert "restricoes_alimentares: nenhuma" in sessao.processar("/perfil restricoes nenhuma")
    saida = sessao.processar("/perfil limpar")
    assert "preferencias_alimentares: nenhuma" in saida
    assert "vegetariana" in sessao.processar("/perfil exemplo")
    assert "Uso inválido" in sessao.processar("/perfil xpto")


def test_chat_usa_o_perfil_alterado_na_mensagem_ao_modelo():
    modelo = ModeloFalso()
    sessao = SessaoChat(Cultiva(modelo))
    sessao.processar("/perfil restricoes sem lactose")
    sessao.processar("Por que evitar alimentos ultraprocessados?")
    _, mensagem = modelo.chamadas[-1]
    assert "sem lactose" in mensagem
    assert "vegetariana" not in mensagem


def test_chat_comandos_de_controle():
    sessao = nova_sessao()
    assert sessao.processar("/sair") is None
    assert sessao.processar("   ") == ""
    assert "/sinais" in sessao.processar("/ajuda")
    assert "Comando desconhecido" in sessao.processar("/xpto")


# ---------------------------------------------------------------- configuração


@pytest.fixture
def ambiente_limpo(monkeypatch):
    for variavel in VARIAVEIS:
        monkeypatch.delenv(variavel, raising=False)
    return monkeypatch


def escrever_env(tmp_path, conteudo):
    arquivo = tmp_path / ".env"
    arquivo.write_text(conteudo, encoding="utf-8")
    return arquivo


def test_sem_env_nao_inicia(tmp_path, ambiente_limpo):
    with pytest.raises(ConfiguracaoInvalida, match="cp .env.example .env"):
        carregar_configuracao(tmp_path / ".env")


def test_sem_provedor_nao_inicia(tmp_path, ambiente_limpo):
    with pytest.raises(ConfiguracaoInvalida, match="CULTIVA_PROVEDOR"):
        carregar_configuracao(escrever_env(tmp_path, "# vazio\n"))


def test_provedor_invalido(tmp_path, ambiente_limpo):
    with pytest.raises(ConfiguracaoInvalida, match="inválido"):
        carregar_configuracao(escrever_env(tmp_path, "CULTIVA_PROVEDOR=xpto\n"))


def test_ollama_lista_todas_as_variaveis_que_faltam(tmp_path, ambiente_limpo):
    arquivo = escrever_env(tmp_path, "CULTIVA_PROVEDOR=ollama\nCULTIVA_MODELO=\n")
    with pytest.raises(ConfiguracaoInvalida) as erro:
        carregar_configuracao(arquivo)
    assert "CULTIVA_MODELO" in str(erro.value)
    assert "CULTIVA_OLLAMA_URL" in str(erro.value)


def test_ollama_completo_cria_o_modelo(tmp_path, ambiente_limpo):
    arquivo = escrever_env(
        tmp_path,
        "CULTIVA_PROVEDOR=ollama\nCULTIVA_MODELO='qwen2.5'\nCULTIVA_OLLAMA_URL=http://x:1/\n",
    )
    config = carregar_configuracao(arquivo)
    modelo = criar_modelo(config)
    assert isinstance(modelo, ModeloOllama)
    assert (modelo.nome, modelo.url) == ("qwen2.5", "http://x:1")
    assert config.origem["CULTIVA_MODELO"] == ".env"


def test_ambiente_vence_o_env(tmp_path, ambiente_limpo):
    arquivo = escrever_env(
        tmp_path,
        "CULTIVA_PROVEDOR=ollama\nCULTIVA_MODELO=qwen2.5\nCULTIVA_OLLAMA_URL=http://x:1\n",
    )
    ambiente_limpo.setenv("CULTIVA_MODELO", "outro")
    config = carregar_configuracao(arquivo)
    assert config["CULTIVA_MODELO"] == "outro"
    assert config.origem["CULTIVA_MODELO"] == "ambiente"


def test_provedor_da_linha_de_comando_vence_e_falso_nao_exige_mais_nada(tmp_path, ambiente_limpo):
    arquivo = escrever_env(tmp_path, "CULTIVA_PROVEDOR=ollama\n")
    config = carregar_configuracao(arquivo, provedor="falso")
    assert config.provedor == "falso"
    assert config.origem["CULTIVA_PROVEDOR"] == "linha de comando"
    assert isinstance(criar_modelo(config), ModeloFalso)
