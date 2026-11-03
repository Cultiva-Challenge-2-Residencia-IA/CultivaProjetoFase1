import pytest

from broker.allowlist_campos import AllowlistInvalida, carregar_allowlist
from broker.context_broker import AgenteSemPermissao, ContextBroker
from dominio.exemplos import PERFIL_EXEMPLO, REGISTROS_EXEMPLO
from dominio.modelos import Aba
from orquestracao.roteador import aba_de_destino


def test_broker_entrega_so_a_propria_aba_e_preferencias():
    contexto = ContextBroker().contexto_para("nutricao", PERFIL_EXEMPLO, REGISTROS_EXEMPLO)
    assert set(contexto.perfil) == {"preferencias_alimentares", "restricoes_alimentares"}
    assert contexto.registros
    assert all(r.aba is Aba.NUTRICAO for r in contexto.registros)
    assert set(contexto.metas) == {Aba.NUTRICAO}


def test_broker_nunca_entrega_dados_pessoais():
    contexto = ContextBroker().contexto_para("nutricao", PERFIL_EXEMPLO, REGISTROS_EXEMPLO)
    conteudo = repr(contexto)
    for dado in (PERFIL_EXEMPLO.nome, PERFIL_EXEMPLO.email, PERFIL_EXEMPLO.telefone):
        assert dado not in conteudo


def test_broker_recusa_agente_sem_allowlist():
    with pytest.raises(AgenteSemPermissao):
        ContextBroker().contexto_para("estudos", PERFIL_EXEMPLO, REGISTROS_EXEMPLO)


def test_allowlist_com_campo_proibido_falha(tmp_path):
    arquivo = tmp_path / "allowlist.yaml"
    arquivo.write_text(
        "nunca: [email]\nagentes:\n  nutricao:\n    perfil: [email]\n", encoding="utf-8"
    )
    with pytest.raises(AllowlistInvalida):
        carregar_allowlist(arquivo)


@pytest.mark.parametrize(
    ("mensagem", "destino"),
    [
        ("Qual o melhor treino de academia?", Aba.SAUDE_FISICA),
        ("Como organizar meus estudos para a prova?", Aba.ESTUDOS),
        ("O que comer antes do treino?", None),  # tem termo da Nutrição: fica
        ("Oi, tudo bem?", None),  # sem termo de nenhuma Aba: fica
        ("Provavelmente vou almoçar fora", None),
    ],
)
def test_roteador(mensagem, destino):
    assert aba_de_destino(mensagem, Aba.NUTRICAO) == destino
