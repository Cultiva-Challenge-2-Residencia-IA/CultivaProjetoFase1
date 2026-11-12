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
