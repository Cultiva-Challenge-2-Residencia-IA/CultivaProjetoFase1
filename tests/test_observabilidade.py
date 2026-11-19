from src import observabilidade
from src.models.schemas import RetrievedChunk


def test_observabilidade_desligada_nos_testes():
    assert observabilidade.ativo() is False


def test_observacao_nula_aceita_a_api_usada_no_codigo():
    with observabilidade.atributos_do_trace(trace_name="x", tags=["t"]):
        with observabilidade.observacao("consult", input={"q": "x"}) as obs:
            obs.update(output="ok", metadata={"a": 1}, level="ERROR", status_message="m")
            obs.update(usage_details={"input": 1, "output": 2})
            obs.score_trace(name="s", value=1.0, data_type="NUMERIC")
    observabilidade.flush()


def test_consulta_funciona_sem_langfuse():
    from src.agent.consultant_baseline import NutritionConsultantBaseline

    consultor = NutritionConsultantBaseline(enable_ollama=False)
    resposta = consultor.consult("Quais alimentos são fontes de fibras?")
    assert resposta.model_used == "local_extractive_synthesis"
    assert resposta.retrieved_chunks


def test_resumo_trechos_nao_inclui_texto():
    from src.agent.consultant_baseline import NutritionConsultantBaseline

    consultor = NutritionConsultantBaseline(enable_ollama=False)
    retrieved = consultor.retriever.retrieve("fibras alimentares", top_k=2)
    resumo = observabilidade.resumo_trechos(retrieved)
    assert [item["posicao"] for item in resumo] == [1, 2]
    assert all(isinstance(item, dict) for item in resumo)
    assert all("raw_text" not in item for item in resumo)
    assert isinstance(retrieved[0], RetrievedChunk)


# --- Privacidade (revisão do PR do Langfuse; ADR 0003) ------------------------------------------


def test_destino_padrao_e_local_e_externo_exige_liberacao():
    from src import config

    assert config.destino_local("http://localhost:3000")
    assert config.destino_local("http://127.0.0.1:3000")
    assert not config.destino_local("https://us.cloud.langfuse.com")
    assert not config.destino_local("https://langfuse.equipe.exemplo.org")
    assert config.langfuse_liberado(True, "http://localhost:3000", permitir_externo=False)
    assert not config.langfuse_liberado(True, "https://us.cloud.langfuse.com", permitir_externo=False)
    assert config.langfuse_liberado(True, "https://us.cloud.langfuse.com", permitir_externo=True)
    assert not config.langfuse_liberado(False, "http://localhost:3000", permitir_externo=True)


def test_mascarar_estrutura_alcanca_textos_aninhados():
    dado = {
        "query": "meu e-mail é ana@exemplo.com",
        "lista": ["CPF 123.456.789-09", 3],
        "aninhado": {"x": ("tel (11) 98765-4321",)},
    }
    mascarado = observabilidade.mascarar_estrutura(dado)
    texto = str(mascarado)
    assert "ana@exemplo.com" not in texto and "123.456.789-09" not in texto and "98765-4321" not in texto
    assert mascarado["lista"][1] == 3


def test_cliente_usa_destino_da_configuracao_e_mascara(monkeypatch):
    """Com o Langfuse ligado, o cliente nunca usa o destino padrão do SDK (a nuvem) e sempre mascara."""
    import contextlib
    import importlib
    import sys
    import types

    from src import config

    capturado = {}

    class LangfuseFalso:
        def __init__(self, **kwargs):
            capturado.update(kwargs)

    falso = types.ModuleType("langfuse")
    falso.Langfuse = LangfuseFalso
    falso.propagate_attributes = lambda **_: contextlib.nullcontext()
    monkeypatch.setitem(sys.modules, "langfuse", falso)
    monkeypatch.setattr(config, "LANGFUSE_ATIVO", True)
    monkeypatch.setattr(config, "LANGFUSE_BASE_URL", "http://localhost:3000")
    try:
        importlib.reload(observabilidade)
        assert capturado["base_url"] == "http://localhost:3000"
        assert capturado["mask"](data={"q": "CPF 123.456.789-09"}) == {"q": "CPF [CPF]"}
    finally:
        monkeypatch.undo()
        importlib.reload(observabilidade)
    assert observabilidade.ativo() is False


def test_mensagem_de_risco_nunca_entra_no_trace(monkeypatch):
    import contextlib

    from src.agent import consultant_baseline as cb

    registrado = []

    class Obs:
        def update(self, **kwargs):
            registrado.append(kwargs)

        def score_trace(self, **kwargs):
            registrado.append(kwargs)

    @contextlib.contextmanager
    def observacao_falsa(nome, tipo="span", **kwargs):
        registrado.append({"nome": nome, **kwargs})
        yield Obs()

    monkeypatch.setattr(cb, "observacao", observacao_falsa)
    mensagem = "Vomito depois de comer para não engordar."
    consultor = cb.NutritionConsultantBaseline(enable_ollama=False)
    resposta = consultor.consult(mensagem)

    assert resposta.risk_triggered
    assert mensagem not in str(registrado)
    assert registrado[0]["input"]["risco_categorias"] == resposta.risk_categories
