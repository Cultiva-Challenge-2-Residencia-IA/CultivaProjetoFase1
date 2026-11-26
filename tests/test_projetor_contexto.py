"""Projetor de contexto, Fatos do Usuário e janela do Histórico por tokens (issue #112, ADR 0005).

Junção principal: o serviço de chat, com Agentes de área e LLM falsos. O teste olha o que o agente
recebeu, o que a resposta mostra e o que fica guardado ou apagado.
"""

from typing import List

import pytest

from src.chat.historico import HistoricoSQLite
from src.chat.servico import CHAT_GERAL, ServicoDeChat
from src.models.schemas import ConsultantResponse
from src.orquestrador.roteamento import AREA_NUTRICAO, AREA_SAUDE_FISICA


class AgenteFalso:
    def __init__(self, area: str):
        self.area = area
        self.chamadas: List[dict] = []

    def responder(self, pergunta, top_k, consultas_extras, historico, fatos=()):
        self.chamadas.append({"pergunta": pergunta, "extras": list(consultas_extras),
                              "historico": list(historico), "fatos": list(fatos)})
        return ConsultantResponse(
            response_id=f"r-{self.area}-{len(self.chamadas)}", original_query=pergunta, effective_query=pergunta,
            guardrail_triggered=False, intent_category="SAFE_EVIDENCE_QUERY",
            evidence_summary=("Primeira frase longa da resposta sobre o tema [T1]. Segunda frase [T1]. "
                              "Terceira frase que não deve entrar no Histórico [T1]. " * 30),
            physiological_mechanism="", protocol_findings="",
            evidence_grade="N/A", corpus_version="c", prompt_version="p", model_version="m", fontes_version="f",
        )


@pytest.fixture
def agentes():
    return {AREA_NUTRICAO: AgenteFalso(AREA_NUTRICAO), AREA_SAUDE_FISICA: AgenteFalso(AREA_SAUDE_FISICA)}


def _servico(tmp_path, agentes, llm=None, **kwargs) -> ServicoDeChat:
    return ServicoDeChat(agentes=agentes, historico=HistoricoSQLite(tmp_path / "conversas.sqlite3"), llm=llm,
                         **kwargs)


def test_historico_cabe_no_orcamento_de_tokens_com_respostas_encurtadas(tmp_path, agentes):
    servico = _servico(tmp_path, agentes, orcamento_historico=300)
    for i in range(12):
        servico.enviar(AREA_NUTRICAO, "u1", "c1", f"Pergunta {i} sobre alimentos com fibra?")
    historico = agentes[AREA_NUTRICAO].chamadas[-1]["historico"]
    assert sum(len(m.texto) for m in historico) <= 300 * 4
    assert historico[-1].texto.startswith("Primeira frase")  # a mais recente entra
    respostas = [m for m in historico if m.papel == "assistente"]
    assert respostas and all("[T" not in m.texto and "Terceira frase" not in m.texto for m in respostas)
    # Com respostas encurtadas, cabem mais mensagens do que as 6 de antes.
    assert len(historico) > 6


def _sincrono(tarefa):
    tarefa()


class LLMFalso:
    """Responde à extração de fatos com o que o teste mandar e devolve None ao resto (reescrita e
    Sincronizador caem no caminho determinístico)."""

    def __init__(self, fatos=None, selecao=None):
        self.fatos = fatos or []
        self.selecao = selecao
        self.pedidos: List[tuple] = []

    def __call__(self, sistema, usuario):
        self.pedidos.append((sistema, usuario))
        if "Fatos do Usuário" in sistema and "extrai" in sistema:
            return {"fatos": self.fatos}
        if self.selecao is not None and "fatos_candidatos" in usuario:
            return self.selecao
        return None


def _com_memoria(tmp_path, agentes, llm, saude=False, **kwargs):
    servico = _servico(tmp_path, agentes, llm=llm, executar_em_segundo_plano=_sincrono, **kwargs)
    servico.definir_consentimento("u1", memoria=True, saude=saude)
    return servico


def test_sem_consentimento_nenhum_fato_e_guardado(tmp_path, agentes):
    llm = LLMFalso(fatos=[{"categoria": "atividade_praticada", "texto": "pratica musculação"}])
    servico = _servico(tmp_path, agentes, llm=llm, executar_em_segundo_plano=_sincrono)
    servico.enviar(AREA_SAUDE_FISICA, "u1", "c1", "Eu faço musculação, quantas séries são indicadas?")
    assert servico.listar_fatos("u1") == []
    assert not any("extrai" in s for s, _ in llm.pedidos)


def test_com_consentimento_fato_da_mensagem_do_usuario_e_guardado_pela_area_do_assunto(tmp_path, agentes):
    llm = LLMFalso(fatos=[{"categoria": "atividade_praticada", "texto": "pratica musculação 4 vezes por semana"}])
    servico = _com_memoria(tmp_path, agentes, llm)
    servico.enviar(AREA_NUTRICAO, "u1", "c1", "Treino musculação 4 vezes por semana, o que comer antes?")
    fatos = servico.listar_fatos("u1")
    assert [(f.categoria, f.area, f.texto) for f in fatos] == [
        ("atividade_praticada", AREA_SAUDE_FISICA, "pratica musculação 4 vezes por semana")]
    # A extração só leu a mensagem do Usuário, nunca a resposta do assistente.
    _, entrada = next(p for p in llm.pedidos if "extrai" in p[0])
    assert "Treino musculação" in entrada and "Primeira frase longa" not in entrada


def test_condicao_de_saude_exige_consentimento_separado(tmp_path, agentes):
    llm = LLMFalso(fatos=[{"categoria": "condicao_saude", "texto": "tem diabetes tipo 2"},
                          {"categoria": "padrao_alimentar", "texto": "é vegetariana"}])
    servico = _com_memoria(tmp_path, agentes, llm, saude=False)
    servico.enviar(AREA_NUTRICAO, "u1", "c1", "Sou vegetariana e tenho diabetes tipo 2, posso comer arroz?")
    assert [f.categoria for f in servico.listar_fatos("u1")] == ["padrao_alimentar"]


def test_mensagem_de_portao_nunca_vira_fato(tmp_path, agentes):
    llm = LLMFalso(fatos=[{"categoria": "padrao_alimentar", "texto": "vomita depois de comer"}])
    servico = _com_memoria(tmp_path, agentes, llm)
    servico.enviar(CHAT_GERAL, "u1", "c1", "Vomito depois de comer para não engordar.")
    assert servico.listar_fatos("u1") == []


def test_categoria_fora_do_esquema_e_descartada(tmp_path, agentes):
    llm = LLMFalso(fatos=[{"categoria": "renda_mensal", "texto": "ganha pouco"}])
    servico = _com_memoria(tmp_path, agentes, llm)
    servico.enviar(AREA_NUTRICAO, "u1", "c1", "Quais alimentos baratos têm fibra?")
    assert servico.listar_fatos("u1") == []


class Relogio:
    def __init__(self):
        from datetime import datetime, timezone
        self.agora = datetime(2026, 11, 25, tzinfo=timezone.utc)

    def __call__(self):
        return self.agora

    def avancar(self, dias):
        from datetime import timedelta
        self.agora += timedelta(days=dias)


def test_fato_novo_da_mesma_categoria_substitui_o_anterior(tmp_path, agentes):
    llm = LLMFalso(fatos=[{"categoria": "frequencia_treino", "texto": "treina 4 vezes por semana"}])
    relogio = Relogio()
    servico = _com_memoria(tmp_path, agentes, llm, relogio=relogio)
    servico.enviar(AREA_SAUDE_FISICA, "u1", "c1", "Treino 4 vezes por semana, quanto descansar?")
    relogio.avancar(10)
    llm.fatos = [{"categoria": "frequencia_treino", "texto": "parou de treinar"}]
    servico.enviar(AREA_SAUDE_FISICA, "u1", "c1", "Parei de treinar, como voltar aos poucos?")
    assert [f.texto for f in servico.listar_fatos("u1")] == ["parou de treinar"]


def test_fato_sem_atualizacao_expira_depois_do_prazo(tmp_path, agentes):
    llm = LLMFalso(fatos=[{"categoria": "padrao_alimentar", "texto": "é vegetariana"}])
    relogio = Relogio()
    servico = _com_memoria(tmp_path, agentes, llm, relogio=relogio, prazo_fatos_dias=90)
    servico.enviar(AREA_NUTRICAO, "u1", "c1", "Sou vegetariana, de onde tirar ferro?")
    relogio.avancar(89)
    assert len(servico.listar_fatos("u1")) == 1
    relogio.avancar(2)
    assert servico.listar_fatos("u1") == []


def test_apagar_conversa_usuario_ou_fato_apaga_os_fatos(tmp_path, agentes):
    llm = LLMFalso(fatos=[{"categoria": "padrao_alimentar", "texto": "é vegetariana"}])
    servico = _com_memoria(tmp_path, agentes, llm)
    servico.enviar(AREA_NUTRICAO, "u1", "c1", "Sou vegetariana, de onde tirar ferro?")
    servico.apagar_conversa("u1", "c1")
    assert servico.listar_fatos("u1") == []

    servico.enviar(AREA_NUTRICAO, "u1", "c2", "Sou vegetariana, de onde tirar ferro?")
    fato = servico.listar_fatos("u1")[0]
    assert servico.apagar_fato("u2", fato.id) == 0  # fato de outro Usuário não é apagado
    assert servico.apagar_fato("u1", fato.id) == 1
    assert servico.listar_fatos("u1") == []

    servico.enviar(AREA_NUTRICAO, "u1", "c3", "Sou vegetariana, de onde tirar ferro?")
    servico.apagar_usuario("u1")
    assert servico.listar_fatos("u1") == []
    assert servico.consentimento("u1") == (False, False)


def test_revogar_o_consentimento_para_a_extracao_e_o_uso(tmp_path, agentes):
    llm = LLMFalso(fatos=[{"categoria": "padrao_alimentar", "texto": "é vegetariana"}])
    servico = _com_memoria(tmp_path, agentes, llm)
    servico.enviar(AREA_NUTRICAO, "u1", "c1", "Sou vegetariana, de onde tirar ferro?")
    servico.definir_consentimento("u1", memoria=False)
    # A pessoa continua vendo o que ficou guardado, para pedir a exclusão (LGPD, art. 9º).
    assert [f.texto for f in servico.listar_fatos("u1")] == ["é vegetariana"]
    pedidos_antes = len(llm.pedidos)
    servico.enviar(AREA_NUTRICAO, "u1", "c1", "Sou vegana agora, e o cálcio?")
    assert not any("extrai" in s for s, _ in llm.pedidos[pedidos_antes:])


def _guardar(servico, usuario, categoria, texto, conversa="c0"):
    servico.fatos.registrar(usuario, conversa, categoria, texto, servico.relogio())
    return next(f for f in servico.listar_fatos(usuario) if f.texto == texto)


def _selecao(area, pergunta, ids):
    return {"pergunta_completa": pergunta,
            "subperguntas": [{"area": area, "pergunta": pergunta, "trecho_hipotetico": "", "fatos": ids}]}


def test_fato_relacionado_chega_ao_agente_e_o_nao_relacionado_nao(tmp_path, agentes):
    llm = LLMFalso()
    servico = _com_memoria(tmp_path, agentes, llm)
    treino = _guardar(servico, "u1", "atividade_praticada", "pratica musculação 4 vezes por semana")
    _guardar(servico, "u1", "restricao_alergia", "tem alergia a amendoim")
    pergunta = "Quanta proteína comer por dia?"
    llm.selecao = _selecao(AREA_NUTRICAO, pergunta, [treino.id])
    resposta = servico.enviar(AREA_NUTRICAO, "u1", "c1", pergunta)
    assert [f.texto for f in agentes[AREA_NUTRICAO].chamadas[-1]["fatos"]] == ["pratica musculação 4 vezes por semana"]
    assert [f["texto"] for f in resposta.fatos_usados] == ["pratica musculação 4 vezes por semana"]
    assert servico.fatos.entregas("u1") == [(treino.id, AREA_NUTRICAO, "c1")]
    # Os candidatos foram à reescrita (a escolha é do LLM, na mesma chamada).
    assert any("fatos_candidatos" in u and "amendoim" in u for _, u in llm.pedidos)


def test_sem_llm_nenhum_fato_e_entregue(tmp_path, agentes):
    servico = _com_memoria(tmp_path, agentes, llm=None)
    _guardar(servico, "u1", "atividade_praticada", "pratica musculação")
    resposta = servico.enviar(AREA_NUTRICAO, "u1", "c1", "Quanta proteína comer por dia?")
    assert agentes[AREA_NUTRICAO].chamadas[-1]["fatos"] == []
    assert resposta.fatos_usados == []


def test_id_inventado_pelo_llm_e_ignorado(tmp_path, agentes):
    llm = LLMFalso()
    servico = _com_memoria(tmp_path, agentes, llm)
    _guardar(servico, "u1", "atividade_praticada", "pratica musculação")
    llm.selecao = _selecao(AREA_NUTRICAO, "Quanta proteína?", [999])
    servico.enviar(AREA_NUTRICAO, "u1", "c1", "Quanta proteína comer por dia?")
    assert agentes[AREA_NUTRICAO].chamadas[-1]["fatos"] == []


def test_sem_consentimento_os_fatos_guardados_nao_sao_usados(tmp_path, agentes):
    llm = LLMFalso()
    servico = _com_memoria(tmp_path, agentes, llm)
    treino = _guardar(servico, "u1", "atividade_praticada", "pratica musculação")
    servico.definir_consentimento("u1", memoria=False)
    llm.selecao = _selecao(AREA_NUTRICAO, "Quanta proteína?", [treino.id])
    servico.enviar(AREA_NUTRICAO, "u1", "c1", "Quanta proteína comer por dia?")
    assert agentes[AREA_NUTRICAO].chamadas[-1]["fatos"] == []
    assert not any("fatos_candidatos" in u for _, u in llm.pedidos)


def test_condicao_de_saude_so_vai_com_consentimento_e_orienta_a_busca(tmp_path, agentes):
    llm = LLMFalso()
    servico = _com_memoria(tmp_path, agentes, llm, saude=True)
    diabetes = _guardar(servico, "u1", "condicao_saude", "tem diabetes tipo 2")
    pergunta = "Quantos minutos de caminhada por semana?"
    llm.selecao = _selecao(AREA_SAUDE_FISICA, pergunta, [diabetes.id])
    servico.enviar(AREA_SAUDE_FISICA, "u1", "c1", pergunta)
    chamada = agentes[AREA_SAUDE_FISICA].chamadas[-1]
    assert [f.texto for f in chamada["fatos"]] == ["tem diabetes tipo 2"]
    assert any("tem diabetes tipo 2" in extra for extra in chamada["extras"])

    servico.definir_consentimento("u1", memoria=True, saude=False)
    llm.pedidos.clear()
    servico.enviar(AREA_SAUDE_FISICA, "u1", "c2", pergunta)
    assert agentes[AREA_SAUDE_FISICA].chamadas[-1]["fatos"] == []
    assert not any("diabetes" in u for _, u in llm.pedidos)


# Checagem de citação por frase: o marcador [CONTEXTO] (Fato do Usuário) -------------------------

from src.rag.verificador.citacoes import normalizar_frases_citadas, verificar_citacoes  # noqa: E402


def _campos(frase):
    return {"evidence_summary": frase, "physiological_mechanism": "", "protocol_findings": ""}


def test_contexto_com_trecho_e_fato_entregue_e_aceito():
    v = verificar_citacoes(_campos("Como você treina 4 vezes por semana, a proteína ajuda na recuperação [CONTEXTO][T1]."),
                           n_trechos=1, tem_contexto=True)
    assert v.valida and v.trechos_citados == [1]


def test_contexto_sem_fato_entregue_e_marcador_invalido():
    v = verificar_citacoes(_campos("Como você treina 4 vezes por semana, a proteína ajuda [CONTEXTO][T1]."),
                           n_trechos=1)
    assert not v.valida and "[CONTEXTO]" in v.marcadores_invalidos


def test_frase_so_com_contexto_e_reprovada_porque_afirmacao_de_saude_exige_trecho():
    v = verificar_citacoes(_campos("Você treina musculação 4 vezes por semana e precisa de mais proteína [CONTEXTO]."),
                           n_trechos=1, tem_contexto=True)
    assert not v.valida and v.frases_so_contexto


def test_formato_estruturado_aceita_contexto_entre_os_trechos():
    texto = normalizar_frases_citadas({"evidence_summary": [
        {"frase": "Como você treina, a proteína ajuda na recuperação muscular.", "trechos": ["CONTEXTO", 1]}]})
    assert texto["evidence_summary"].endswith("[CONTEXTO][T1].")


def test_marcador_de_contexto_nao_aparece_no_texto_exibido(tmp_path, agentes):
    class AgenteQueUsaContexto(AgenteFalso):
        def responder(self, pergunta, top_k, consultas_extras, historico, fatos=()):
            r = super().responder(pergunta, top_k, consultas_extras, historico, fatos)
            return r.model_copy(update={"evidence_summary": "Como você treina, a proteína ajuda na recuperação [CONTEXTO][T1]."})

    agentes[AREA_NUTRICAO] = AgenteQueUsaContexto(AREA_NUTRICAO)
    resposta = _servico(tmp_path, agentes).enviar(AREA_NUTRICAO, "u1", "c1", "Quanta proteína comer por dia?")
    assert "[CONTEXTO]" not in resposta.texto
    assert "[CONTEXTO]" in resposta.texto_com_marcadores


# Síntese do Agente de área com Fatos do Usuário: prompt e checagem de citação ---------------------

from tests.test_citacoes import _cliente_com_llm, _trechos  # noqa: E402

_RESPOSTA_COM_CONTEXTO = {
    "evidence_summary": [{"frase": "Como você treina com frequência, vale saber que ultraprocessados aumentam o risco de obesidade.",
                          "trechos": ["CONTEXTO", 1], "citacao": "A ingestão aumenta o risco de obesidade"}],
    "physiological_mechanism": [], "protocol_findings": []}


def test_sintese_com_fato_entregue_aceita_contexto_e_o_prompt_traz_os_fatos():
    cliente = _cliente_com_llm(_RESPOSTA_COM_CONTEXTO)
    prompts = []
    original = cliente._call_ollama_model
    cliente._call_ollama_model = lambda modelo, prompt: prompts.append(prompt) or original(modelo, prompt)
    resultado, modelo = cliente.generate_structured_synthesis(
        "ultraprocessados", _trechos(), fatos="- pratica musculação 4 vezes por semana")
    assert resultado["_fundamentacao"]["status"] == "llm_citacoes_validas"
    assert "[CONTEXTO]" in resultado["evidence_summary"]
    assert "pratica musculação 4 vezes por semana" in prompts[0]
    assert "nunca fonte" in prompts[0].lower()


def test_sintese_sem_fato_entregue_bloqueia_o_contexto():
    cliente = _cliente_com_llm(_RESPOSTA_COM_CONTEXTO)
    resultado, modelo = cliente.generate_structured_synthesis("ultraprocessados", _trechos())
    assert modelo == "local_extractive_synthesis" or resultado["_fundamentacao"]["status"] != "llm_citacoes_validas"
    assert "[CONTEXTO]" not in str(resultado.get("evidence_summary"))


def test_prompt_sem_fatos_fica_igual_ao_de_antes():
    cliente = _cliente_com_llm(_RESPOSTA_COM_CONTEXTO)
    assert "FATOS DO USUÁRIO" not in cliente._build_user_prompt("ultraprocessados", _trechos())


# API: consentimento, listagem e exclusão de fatos (com o token da issue #108) --------------------

from fastapi.testclient import TestClient  # noqa: E402

import src.api as api  # noqa: E402
from src.chat.autenticacao import emitir_token  # noqa: E402

SEGREDO = "segredo-de-teste-com-pelo-menos-32-caracteres"


def _cabecalho(usuario_id):
    return {"Authorization": f"Bearer {emitir_token(usuario_id, SEGREDO.encode())}"}


@pytest.fixture
def cliente_e_servico(tmp_path, agentes, monkeypatch):
    llm = LLMFalso(fatos=[{"categoria": "padrao_alimentar", "texto": "é vegetariana"}])
    servico = _servico(tmp_path, agentes, llm=llm, executar_em_segundo_plano=_sincrono)
    monkeypatch.setenv("CULTIVA_AUTH_SEGREDO", SEGREDO)
    monkeypatch.setattr(api, "get_servico_de_chat", lambda: servico)
    monkeypatch.setattr(api, "save_response_trace", lambda resposta: None)
    return TestClient(api.app), servico


def test_api_aceite_listagem_e_exclusao_de_fatos(cliente_e_servico):
    cliente, servico = cliente_e_servico
    r = cliente.put("/chat/usuarios/u1/memoria", json={"memoria": True, "saude": False}, headers=_cabecalho("u1"))
    assert r.status_code == 200 and r.json() == {"memoria": True, "saude": False}
    cliente.post("/chat/nutricao", json={"conversa_id": "c1", "mensagem": "Sou vegetariana, de onde tirar ferro?"},
                 headers=_cabecalho("u1"))
    fatos = cliente.get("/chat/usuarios/u1/fatos", headers=_cabecalho("u1")).json()["fatos"]
    assert [f["texto"] for f in fatos] == ["é vegetariana"]
    # Outro Usuário não lê nem apaga.
    assert cliente.get("/chat/usuarios/u1/fatos", headers=_cabecalho("u2")).status_code == 403
    assert cliente.delete(f"/chat/usuarios/u1/fatos/{fatos[0]['id']}", headers=_cabecalho("u2")).status_code == 403
    r = cliente.delete(f"/chat/usuarios/u1/fatos/{fatos[0]['id']}", headers=_cabecalho("u1"))
    assert r.json() == {"apagados": 1}
    assert cliente.get("/chat/usuarios/u1/fatos", headers=_cabecalho("u1")).json()["fatos"] == []


def test_api_sem_token_recusa_os_endpoints_de_fatos(cliente_e_servico):
    cliente, _ = cliente_e_servico
    assert cliente.get("/chat/usuarios/u1/fatos").status_code == 401
    assert cliente.put("/chat/usuarios/u1/memoria", json={"memoria": True}).status_code == 401


def test_texto_dos_fatos_nao_vai_ao_langfuse(tmp_path, agentes):
    from src.observabilidade import mascarar_estrutura

    llm = LLMFalso(fatos=[{"categoria": "condicao_saude", "texto": "tem hipotireoidismo desde 2019"}])
    servico = _com_memoria(tmp_path, agentes, llm, saude=True)
    servico.enviar(AREA_NUTRICAO, "u1", "c1", "Tenho hipotireoidismo desde 2019, posso comer soja?")
    registrado = mascarar_estrutura({"messages": [{"content": "FATOS: - tem hipotireoidismo desde 2019"}]})
    assert "hipotireoidismo" not in str(registrado)
    assert "[fato do usuário: condicao_saude]" in str(registrado)


def test_condicao_de_saude_entregue_traz_o_encaminhamento_mesmo_sem_redacao(tmp_path, agentes):
    llm = LLMFalso()
    servico = _com_memoria(tmp_path, agentes, llm, saude=True)
    diabetes = _guardar(servico, "u1", "condicao_saude", "tem diabetes tipo 2")
    llm.selecao = _selecao(AREA_NUTRICAO, "Posso comer chocolate?", [diabetes.id])
    r = servico.enviar(AREA_NUTRICAO, "u1", "c1", "Posso comer chocolate?")
    assert r.texto.endswith("vale conversar com um profissional de saúde sobre o que faz sentido para você.")


# Correções da revisão de código ----------------------------------------------------------------

def test_duas_alergias_na_mesma_mensagem_ficam_as_duas(tmp_path, agentes):
    llm = LLMFalso(fatos=[{"categoria": "restricao_alergia", "texto": "tem alergia a amendoim"},
                          {"categoria": "restricao_alergia", "texto": "tem intolerância à lactose"}])
    servico = _com_memoria(tmp_path, agentes, llm)
    servico.enviar(AREA_NUTRICAO, "u1", "c1", "Tenho alergia a amendoim e intolerância à lactose, o que comer?")
    assert sorted(f.texto for f in servico.listar_fatos("u1")) == ["tem alergia a amendoim", "tem intolerância à lactose"]


def test_extracao_atrasada_nao_grava_depois_da_exclusao_nem_da_revogacao(tmp_path, agentes):
    pendentes = []
    llm = LLMFalso(fatos=[{"categoria": "padrao_alimentar", "texto": "é vegetariana"}])
    servico = _servico(tmp_path, agentes, llm=llm, executar_em_segundo_plano=pendentes.append)
    servico.definir_consentimento("u1", memoria=True)
    servico.enviar(AREA_NUTRICAO, "u1", "c1", "Sou vegetariana, de onde tirar ferro?")
    servico.apagar_usuario("u1")
    pendentes.pop()()
    assert servico.listar_fatos("u1") == []

    servico.definir_consentimento("u2", memoria=True)
    servico.enviar(AREA_NUTRICAO, "u2", "c2", "Sou vegetariana, de onde tirar ferro?")
    servico.definir_consentimento("u2", memoria=False)
    pendentes.pop()()
    assert servico.listar_fatos("u2") == []


def test_mensagem_longa_nao_zera_o_historico():
    from src.chat.servico import no_orcamento
    from src.orquestrador.reescrita import Mensagem

    longa = Mensagem("usuario", "palavra " * 3000)
    recentes = no_orcamento([Mensagem("usuario", "oi"), longa], orcamento=100)
    assert recentes and recentes[-1].papel == "usuario" and len(recentes[-1].texto) <= 100 * 4
