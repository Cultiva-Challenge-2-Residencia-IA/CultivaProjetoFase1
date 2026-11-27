"""Respostas mais humanas (issue #104): redação final a partir das frases checadas e pergunta de
esclarecimento antes de pedidos vagos ou individuais. Junção: o serviço de chat, com agentes e LLM
falsos."""


import pytest

from src.chat.historico import HistoricoSQLite
from src.chat.servico import ServicoDeChat
from src.models.schemas import ConsultantResponse
from src.orquestrador.roteamento import AREA_NUTRICAO, AREA_SAUDE_FISICA

TEXTO_DO_AGENTE = ("O Guia recomenda evitar alimentos ultraprocessados [T1]. "
                   "Eles costumam ter muito açúcar e gordura [T1]. "
                   "Uma porção de 30 g de chocolate tem cerca de 160 kcal [T2].")


class AgenteFalso:
    def __init__(self, area, status="llm_citacoes_validas"):
        self.area, self.status, self.chamadas = area, status, []

    def responder(self, pergunta, top_k, consultas_extras, historico, fatos=()):
        self.chamadas.append(pergunta)
        return ConsultantResponse(
            response_id=f"r{len(self.chamadas)}", original_query=pergunta, effective_query=pergunta,
            guardrail_triggered=False, intent_category="SAFE_EVIDENCE_QUERY", evidence_summary=TEXTO_DO_AGENTE,
            physiological_mechanism="", protocol_findings="", evidence_grade="N/A", corpus_version="c",
            prompt_version="p", model_version="m", fontes_version="f", fundamentacao_status=self.status)


class LLMFalso:
    def __init__(self, redacao=None, esclarecimento=None):
        self.redacao, self.esclarecimento, self.pedidos = redacao, esclarecimento, []

    def __call__(self, sistema, usuario):
        self.pedidos.append((sistema, usuario))
        if "redator" in sistema.lower():
            return self.redacao
        if "pergunta_completa" in sistema:
            if self.esclarecimento:
                return {"pergunta_completa": "", "subperguntas": [], "esclarecimento": self.esclarecimento}
            return None
        return None


@pytest.fixture
def agentes():
    return {AREA_NUTRICAO: AgenteFalso(AREA_NUTRICAO), AREA_SAUDE_FISICA: AgenteFalso(AREA_SAUDE_FISICA)}


def _servico(tmp_path, agentes, llm, **kwargs):
    return ServicoDeChat(agentes=agentes, historico=HistoricoSQLite(tmp_path / "h.sqlite3"), llm=llm,
                         executar_em_segundo_plano=lambda tarefa: None, redacao=True, **kwargs)


def _redacao(*frases):
    return {"frases": [{"frase": f, "origem": o} for f, o in frases]}


def test_redator_reescreve_e_herda_os_marcadores_das_frases_de_origem(tmp_path, agentes):
    llm = LLMFalso(redacao=_redacao(
        ("Chocolate industrializado entra entre os ultraprocessados, que o Guia recomenda evitar.", [1]),
        ("Eles costumam ter bastante açúcar e gordura.", [2])))
    r = _servico(tmp_path, agentes, llm).enviar(AREA_NUTRICAO, "u1", "c1", "Chocolate faz mal?")
    assert r.texto_com_marcadores.startswith("Chocolate industrializado entra entre os ultraprocessados")
    assert r.texto_com_marcadores.count("[T1]") == 2 and "[T2]" not in r.texto_com_marcadores
    assert r.redacao == "aceita"
    assert r.texto_antes_da_redacao.startswith("O Guia recomenda evitar alimentos ultraprocessados [T1].")


def test_redacao_com_numero_que_nao_esta_na_origem_e_recusada(tmp_path, agentes):
    llm = LLMFalso(redacao=_redacao(("Uma barra de 25 g tem pouco açúcar.", [1])))
    r = _servico(tmp_path, agentes, llm).enviar(AREA_NUTRICAO, "u1", "c1", "Chocolate faz mal?")
    assert r.texto_com_marcadores.startswith("O Guia recomenda evitar")
    assert r.redacao == "recusada"


def test_redacao_que_aponta_origem_inexistente_ou_sem_origem_e_recusada(tmp_path, agentes):
    for redacao in (_redacao(("Frase inventada sobre chocolate.", [9])), _redacao(("Frase sem origem.", []))):
        r = _servico(tmp_path, agentes, LLMFalso(redacao=redacao)).enviar(
            AREA_NUTRICAO, "u1", f"c-{len(redacao['frases'][0]['origem'])}", "Chocolate faz mal?")
        assert r.redacao == "recusada"


def test_numero_com_a_mesma_unidade_da_origem_passa(tmp_path, agentes):
    llm = LLMFalso(redacao=_redacao(("Só para ter ideia, 30 g de chocolate têm cerca de 160 kcal.", [3])))
    r = _servico(tmp_path, agentes, llm).enviar(AREA_NUTRICAO, "u1", "c1", "Chocolate engorda?")
    assert r.redacao == "aceita" and "[T2]" in r.texto_com_marcadores


def test_resposta_extrativa_nao_passa_pelo_redator(tmp_path):
    agentes = {AREA_NUTRICAO: AgenteFalso(AREA_NUTRICAO, status="extrativa"),
               AREA_SAUDE_FISICA: AgenteFalso(AREA_SAUDE_FISICA)}
    llm = LLMFalso(redacao=_redacao(("Qualquer coisa.", [1])))
    r = _servico(tmp_path, agentes, llm).enviar(AREA_NUTRICAO, "u1", "c1", "Chocolate faz mal?")
    assert not any("redator" in s.lower() for s, _ in llm.pedidos)
    assert r.redacao is None


def test_pedido_vago_recebe_pergunta_de_esclarecimento_antes_dos_agentes(tmp_path, agentes):
    llm = LLMFalso(esclarecimento="Você quer ganhar força, resistência ou massa muscular nas pernas?")
    servico = _servico(tmp_path, agentes, llm)
    r = servico.enviar(AREA_SAUDE_FISICA, "u1", "c1", "Quero treinar perna")
    assert r.tipo == "esclarecimento" and r.texto.endswith("?")
    assert not agentes[AREA_SAUDE_FISICA].chamadas
    # A resposta seguinte segue para os agentes, mesmo que a reescrita peça esclarecimento de novo.
    r2 = servico.enviar(AREA_SAUDE_FISICA, "u1", "c1", "Força")
    assert r2.tipo != "esclarecimento" and agentes[AREA_SAUDE_FISICA].chamadas


def test_esclarecimento_invalido_e_ignorado(tmp_path, agentes):
    for texto in ("Tome 2 g de creatina por dia.", "x" * 400 + "?"):
        llm = LLMFalso(esclarecimento=texto)
        r = _servico(tmp_path, agentes, llm).enviar(AREA_NUTRICAO, "u1", f"c{len(texto)}", "Me ajuda com a dieta")
        assert r.tipo != "esclarecimento"


def test_sem_llm_nao_ha_redacao_nem_esclarecimento(tmp_path, agentes):
    r = _servico(tmp_path, agentes, None).enviar(AREA_NUTRICAO, "u1", "c1", "Chocolate faz mal?")
    assert r.redacao is None and r.tipo == "agente"


# Esclarecimento só para pedido vago; nunca pedindo dado pessoal (decisão de 25/11) ----------------

def test_esclarecimento_que_pede_dado_pessoal_e_ignorado(tmp_path, agentes):
    for texto in ("Qual seu objetivo e qual seu nível de atividade física?", "Quanto você pesa e qual sua idade?",
                  "Você pode me mandar seus exames?"):
        r = _servico(tmp_path, agentes, LLMFalso(esclarecimento=texto)).enviar(
            AREA_NUTRICAO, "u1", f"c{len(texto)}", "Quanta proteína devo comer por dia?")
        assert r.tipo != "esclarecimento", texto


def test_prompt_da_reescrita_so_pede_esclarecimento_em_pedido_vago():
    from src.orquestrador.reescrita import SISTEMA_REESCRITA

    assert "vaga" in SISTEMA_REESCRITA and "decisão individual" not in SISTEMA_REESCRITA


# Fatos do Usuário no redator, com [CONTEXTO] checado (Q10) ----------------------------------------

from src.orquestrador.fatos import FatoDoUsuario  # noqa: E402
from src.orquestrador.redator import redigir  # noqa: E402

TREINO = FatoDoUsuario(7, "frequencia_treino", "saude_fisica", "treina musculação 4 vezes por semana", "c0", "2026")
DIABETES = FatoDoUsuario(8, "condicao_saude", "transversal", "tem diabetes tipo 2", "c0", "2026")


def _llm(redacao):
    return lambda sistema, usuario: redacao


def test_redator_relaciona_o_fato_e_a_frase_leva_contexto_e_o_trecho():
    redacao = {"frases": [{"frase": "Como você treina 4 vezes por semana, vale saber que o Guia recomenda evitar ultraprocessados.",
                           "origem": [1], "contexto": [7]}]}
    texto = redigir("Chocolate faz mal?", TEXTO_DO_AGENTE, _llm(redacao), fatos=[TREINO])
    assert texto == "Como você treina 4 vezes por semana, vale saber que o Guia recomenda evitar ultraprocessados [T1][CONTEXTO]."


def test_contexto_com_fato_nao_entregue_e_recusado():
    redacao = {"frases": [{"frase": "Como você treina, evite ultraprocessados.", "origem": [1], "contexto": [99]}]}
    assert redigir("Chocolate faz mal?", TEXTO_DO_AGENTE, _llm(redacao), fatos=[TREINO]) is None


def test_frase_so_com_fato_sem_origem_e_recusada():
    redacao = {"frases": [{"frase": "Você treina 4 vezes por semana.", "origem": [], "contexto": [7]}]}
    assert redigir("Chocolate faz mal?", TEXTO_DO_AGENTE, _llm(redacao), fatos=[TREINO]) is None


def test_condicao_de_saude_no_redator_so_encaminha_e_sem_numero():
    com_numero = {"frases": [{"frase": "Com diabetes, 30 g de chocolate têm 160 kcal.", "origem": [3], "contexto": [8]}]}
    assert redigir("Posso comer chocolate?", TEXTO_DO_AGENTE, _llm(com_numero), fatos=[DIABETES]) is None
    sem_numero = {"frases": [{"frase": "O Guia recomenda evitar ultraprocessados.", "origem": [1]}]}
    texto = redigir("Posso comer chocolate?", TEXTO_DO_AGENTE, _llm(sem_numero), fatos=[DIABETES])
    assert texto.endswith("Como você contou que tem diabetes tipo 2, vale conversar com um profissional de saúde "
                          "sobre o que faz sentido para você.")


def test_redacao_nao_tira_a_nota_legal_quando_o_corpo_fica_vazio(tmp_path):
    class AgenteRestrito(AgenteFalso):
        def responder(self, *a, **k):
            r = super().responder(*a, **k)
            return r.model_copy(update={"guardrail_triggered": True, "legal_compliance_notice": "NOTA LEGAL.",
                                        "evidence_summary": "", "intent_category": "RESTRICTED_DIET_PRESCRIPTION"})

    agentes = {AREA_NUTRICAO: AgenteRestrito(AREA_NUTRICAO), AREA_SAUDE_FISICA: AgenteFalso(AREA_SAUDE_FISICA)}
    llm = LLMFalso(redacao=_redacao(("Qualquer texto.", [1])))
    r = _servico(tmp_path, agentes, llm).enviar(AREA_NUTRICAO, "u1", "c1", "Quantas calorias eu devo comer?")
    assert r.texto.startswith("NOTA LEGAL.")
