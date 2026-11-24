"""Roteamento por regras e portão de sinal de alerta (issue #99)."""

from src.orquestrador.roteamento import AREA_NUTRICAO, AREA_SAUDE_FISICA, rotear_por_regras
from src.guardrails.alerta import MENSAGEM_ALERTA, detectar_sinal_de_alerta


def test_pergunta_so_de_nutricao_vai_para_nutricao():
    rota = rotear_por_regras("Quais alimentos são fontes de fibra?")
    assert rota.areas == [AREA_NUTRICAO]
    assert rota.decidida


def test_pergunta_so_de_saude_fisica_vai_para_saude_fisica():
    rota = rotear_por_regras("Quantos minutos de atividade física por semana um adulto deve fazer?")
    assert rota.areas == [AREA_SAUDE_FISICA]
    assert rota.decidida


def test_pergunta_das_duas_areas_aciona_as_duas():
    rota = rotear_por_regras("O que comer antes do treino e quantas vezes por semana devo treinar musculação?")
    assert set(rota.areas) == {AREA_NUTRICAO, AREA_SAUDE_FISICA}


def test_pergunta_sem_termo_de_area_fica_indecisa():
    rota = rotear_por_regras("Quem ganhou o jogo ontem?")
    assert rota.areas == []
    assert not rota.decidida
    assert not rota.estudos


def test_pergunta_de_estudos_e_reconhecida():
    rota = rotear_por_regras("Como organizar meus estudos para a prova da faculdade?")
    assert rota.estudos
    assert rota.areas == []


def test_dor_no_peito_durante_exercicio_e_sinal_de_alerta():
    sinais = detectar_sinal_de_alerta("Sinto uma dor no peito forte quando corro, é normal?")
    assert sinais
    assert "atendimento" in MENSAGEM_ALERTA.lower()


def test_desmaio_e_sinal_de_alerta():
    assert detectar_sinal_de_alerta("Desmaiei depois do treino de ontem")


def test_pergunta_comum_sobre_exercicio_nao_e_sinal_de_alerta():
    assert detectar_sinal_de_alerta("Quantas séries de agachamento são recomendadas para iniciantes?") == []
    assert detectar_sinal_de_alerta("Sentir falta de ar leve correndo é esperado no começo?") == []


def test_regras_acertam_os_casos_claros_do_dev():
    """Critério 1 de eval/multiagentes/criterios.md: só regras, casos `clara` do dev, acerto >= 0,85."""
    import json
    from pathlib import Path

    casos = json.loads((Path(__file__).resolve().parents[1] / "eval/multiagentes/roteamento.json")
                       .read_text(encoding="utf-8"))["casos"]
    claros = [c for c in casos if c["split"] == "dev" and c["tipo"] == "clara"]
    acertos = sum(sorted(rotear_por_regras(c["mensagem"]).areas) == sorted(c["areas_esperadas"]) for c in claros)
    assert acertos / len(claros) >= 0.85


def test_quebrei_e_apaguei_sem_contexto_de_corpo_nao_sao_sinal_de_alerta():
    # Casos da revisão do PR #100: "quebrei" e "apaguei" em sentido figurado.
    assert detectar_sinal_de_alerta("Quebrei a dieta no fim de semana, o que faço agora?") == []
    assert detectar_sinal_de_alerta("Apaguei o app sem querer e perdi meu cardápio") == []
    assert detectar_sinal_de_alerta("Quebrei meu recorde na corrida!") == []
    assert detectar_sinal_de_alerta("Apaguei a planilha de treino, como refaço?") == []


def test_quebrei_parte_do_corpo_e_apaguei_com_queda_sao_sinal_de_alerta():
    assert detectar_sinal_de_alerta("Acho que quebrei o pé no treino") == ["lesao_aguda"]
    assert detectar_sinal_de_alerta("Caí e quebrei o braço jogando bola") == ["lesao_aguda"]
    assert detectar_sinal_de_alerta("Apaguei durante o treino e caí") == ["desmaio"]
    assert detectar_sinal_de_alerta("Fraturei o tornozelo correndo") == ["lesao_aguda"]
