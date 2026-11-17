from pathlib import Path
import json
import jsonschema

from src.evaluation.benchmark_respostas import (
    carregar_golden_respostas,
    executar_condicao_sem_rag,
    executar_condicao_rag_atual,
    executar_condicao_oracle,
    avaliar_execucao,
    calcular_confrontos_pareados,
    gerar_relatorio_comparativo,
    obter_cliente_langfuse,
    registrar_execucao_langfuse,
    AvaliacaoCaso,
    ExecucaoCondicao,
)
from src.agent.consultant_baseline import NutritionConsultantBaseline


DIRETORIO_RAIZ = Path(__file__).resolve().parent.parent
DIR_RESPOSTAS = DIRETORIO_RAIZ / "eval" / "golden" / "resposta"
SCHEMA_PATH = DIR_RESPOSTAS / "caso_resposta.schema.json"
DEV_PATH = DIR_RESPOSTAS / "dev.json"
TEST_PATH = DIR_RESPOSTAS / "test.json"


def test_schema_json_valido():
    """Valida se o schema existe e é um JSON Schema Draft 2020-12 válido."""
    assert SCHEMA_PATH.exists(), "Schema caso_resposta.schema.json deve existir."
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)


def test_validacao_dev_contra_schema():
    """Valida dev.json estritamente contra o JSON Schema."""
    dados_dev = carregar_golden_respostas(DEV_PATH, SCHEMA_PATH)
    assert dados_dev["versao"] == 1
    assert dados_dev["split"] == "dev"
    assert len(dados_dev["casos"]) >= 6


def test_validacao_test_contra_schema():
    """Valida test.json estritamente contra o JSON Schema."""
    dados_test = carregar_golden_respostas(TEST_PATH, SCHEMA_PATH)
    assert dados_test["versao"] == 1
    assert dados_test["split"] == "test"
    assert len(dados_test["casos"]) >= 6


def test_unicidade_de_ids_entre_splits():
    """Garante que nenhum ID de caso seja duplicado dentro ou entre os splits."""
    dev_casos = carregar_golden_respostas(DEV_PATH)["casos"]
    test_casos = carregar_golden_respostas(TEST_PATH)["casos"]

    ids_dev = [c["id"] for c in dev_casos]
    ids_test = [c["id"] for c in test_casos]

    assert len(ids_dev) == len(set(ids_dev)), f"IDs duplicados em dev: {ids_dev}"
    assert len(ids_test) == len(set(ids_test)), f"IDs duplicados em test: {ids_test}"

    intersecao = set(ids_dev) & set(ids_test)
    assert not intersecao, f"IDs compartilhados entre dev e test: {intersecao}"


def test_consistencia_de_splits():
    """Garante que o campo split de cada caso seja condizente com o arquivo."""
    dev_casos = carregar_golden_respostas(DEV_PATH)["casos"]
    test_casos = carregar_golden_respostas(TEST_PATH)["casos"]

    for c in dev_casos:
        assert c["split"] == "dev", f"Caso {c['id']} em dev.json tem split={c['split']}"
    for c in test_casos:
        assert c["split"] == "test", f"Caso {c['id']} em test.json tem split={c['split']}"


def test_integridade_dos_gabaritos():
    """Valida se fatos atômicos, ressalvas e fontes estão preenchidos corretamente."""
    todos_casos = (
        carregar_golden_respostas(DEV_PATH)["casos"]
        + carregar_golden_respostas(TEST_PATH)["casos"]
    )
    for c in todos_casos:
        assert len(c["pergunta"]) > 5
        assert c["status_corpus"] in ["respondivel_com_corpus", "evidencia_insuficiente", "fora_de_escopo"]
        # Se for caso respondível, deve haver ao menos um fato essencial
        if c["status_corpus"] == "respondivel_com_corpus":
            assert len(c["fatos_essenciais"]) >= 1, f"Caso {c['id']} sem fatos essenciais"
            for f in c["fatos_essenciais"]:
                assert 0.0 < f.get("peso", 1.0) <= 1.0
                assert f["prioridade"] in ["obrigatorio", "importante", "complementar"]
        # Fontes de referência devem ter trechos oracle
        for ref in c.get("fontes_referencia", []):
            assert len(ref["trechos_oracle"]) >= 1


def test_condicao_sem_rag_isolada_sem_ferramentas_nem_contexto():
    """Testa se a condição 'llm_sem_rag' não recebe contexto externo e desativa ferramentas."""
    consultant = NutritionConsultantBaseline(
        enable_ollama=False,
        enable_taco_tool=True,
        enable_graph_engine=True,
    )
    caso_exemplo = carregar_golden_respostas(DEV_PATH)["casos"][0]

    execucao = executar_condicao_sem_rag(caso_exemplo, consultant, usar_llm=False)

    assert execucao.condicao == "llm_sem_rag"
    assert execucao.contexto_fornecido == "", "Condição sem RAG deve ter contexto vazio"
    assert execucao.trechos_recuperados == [], "Condição sem RAG não deve recuperar trechos"
    assert execucao.ferramentas_ativas == [], "Condição sem RAG não deve acionar ferramentas"

    # Avaliação: Fidelidade e Citações devem ser rigorosamente None (N/A)
    avaliacao = avaliar_execucao(caso_exemplo, execucao)
    assert avaliacao.fidelidade_contexto is None, "Fidelidade deve ser N/A na condição sem RAG"
    assert avaliacao.validade_citacoes is None, "Citações devem ser N/A na condição sem RAG"


def test_condicao_oracle_injeta_apenas_fontes_referencia():
    """Testa se a condição 'contexto_oracle' injeta exclusivamente os trechos do gabarito."""
    consultant = NutritionConsultantBaseline(
        enable_ollama=False,
        enable_taco_tool=False,
        enable_graph_engine=False,
    )
    caso_exemplo = carregar_golden_respostas(DEV_PATH)["casos"][0]

    execucao = executar_condicao_oracle(caso_exemplo, consultant, usar_llm=False)

    assert execucao.condicao == "contexto_oracle"
    assert len(execucao.contexto_fornecido) > 0
    # O contexto deve conter os trechos oracle das fontes do caso
    for ref in caso_exemplo["fontes_referencia"]:
        for trecho in ref["trechos_oracle"]:
            assert trecho in execucao.contexto_fornecido

    avaliacao = avaliar_execucao(caso_exemplo, execucao)
    assert avaliacao.fidelidade_contexto is not None, "Fidelidade deve ser calculada para Oracle"


def test_calculo_confrontos_pareados():
    """Testa o cálculo da matriz de confrontos pareados head-to-head."""
    av1 = AvaliacaoCaso(
        caso_id="RESP-01",
        condicao="llm_sem_rag",
        categoria="diretamente_respondivel",
        comportamento_esperado="responder",
        correcao_factual=0.5,
        completude=0.4,
        relevancia=0.8,
        seguranca_ressalvas=1.0,
        fidelidade_contexto=None,
        validade_citacoes=None,
        abstencao_adequada=True,
        erros_criticos_cometidos=[],
        fatos_atendidos=["F01"],
        fatos_ausentes=["F02"],
        nota_geral_ponderada=0.55,
    )
    av2 = AvaliacaoCaso(
        caso_id="RESP-01",
        condicao="rag_atual",
        categoria="diretamente_respondivel",
        comportamento_esperado="responder",
        correcao_factual=0.9,
        completude=0.85,
        relevancia=0.9,
        seguranca_ressalvas=1.0,
        fidelidade_contexto=0.88,
        validade_citacoes=1.0,
        abstencao_adequada=True,
        erros_criticos_cometidos=[],
        fatos_atendidos=["F01", "F02"],
        fatos_ausentes=[],
        nota_geral_ponderada=0.88,
    )
    confrontos = calcular_confrontos_pareados([av1, av2])
    chave = "llm_sem_rag_vs_rag_atual"
    assert chave in confrontos
    assert confrontos[chave]["vitorias_rag_atual"] == 1
    assert confrontos[chave]["vitorias_llm_sem_rag"] == 0
    assert confrontos[chave]["empates"] == 0


def test_integracao_langfuse_mock(mocker):
    """Testa se o envio para o Langfuse registra o trace e os scores corretos sem chamar rede."""
    mock_client = mocker.MagicMock()
    mock_span = mocker.MagicMock()
    mock_client.start_observation.return_value = mock_span
    mock_client.create_trace_id.return_value = "mock-trace-123"

    execucao = ExecucaoCondicao(
        caso_id="RESP-DIR-01",
        condicao="llm_sem_rag",
        pergunta="Pergunta teste",
        modelo="qwen2.5:3b",
        prompt_usuario="Prompt teste",
        contexto_fornecido="",
        resposta_completa={"evidence_summary": "Resumo"},
        resposta_texto_unificado="Resumo",
        trechos_recuperados=[],
        ferramentas_ativas=[],
        guardrail_acionado=False,
        duracao_segundos=1.2,
    )
    avaliacao = AvaliacaoCaso(
        caso_id="RESP-DIR-01",
        condicao="llm_sem_rag",
        categoria="diretamente_respondivel",
        comportamento_esperado="responder",
        correcao_factual=1.0,
        completude=0.8,
        relevancia=0.9,
        seguranca_ressalvas=1.0,
        fidelidade_contexto=None,
        validade_citacoes=None,
        abstencao_adequada=True,
        erros_criticos_cometidos=[],
        fatos_atendidos=["F01"],
        fatos_ausentes=[],
        nota_geral_ponderada=0.92,
    )

    sucesso = registrar_execucao_langfuse(execucao, avaliacao, mock_client, session_id="test_session")
    assert sucesso is True
    assert mock_client.start_observation.called
    assert mock_client.start_observation.call_args.kwargs["trace_context"] == {
        "trace_id": "mock-trace-123"
    }
    assert mock_span.end.called
    # Verifica que scores foram registrados
    score_names = [call.kwargs.get("name") for call in mock_client.create_score.call_args_list]
    assert all(
        call.kwargs.get("trace_id") == "mock-trace-123"
        for call in mock_client.create_score.call_args_list
    )
    assert "correcao_factual" in score_names
    assert "completude" in score_names
    assert "nota_geral_ponderada" in score_names
    # Fidelidade e citações não devem ter sido chamadas pois são None
    assert "fidelidade_contexto" not in score_names


def test_geracao_relatorio_com_incerteza_e_diagnostico_secundario():
    """Valida o cálculo do intervalo de incerteza (IC 95%) e a estratificação do diagnóstico de recuperação."""
    ex_rag_1 = ExecucaoCondicao(
        caso_id="RESP-01",
        condicao="rag_atual",
        pergunta="Pergunta 1",
        modelo="qwen2.5:3b",
        prompt_usuario="P1",
        contexto_fornecido="Contexto 1",
        resposta_completa={"evidence_summary": "S1"},
        resposta_texto_unificado="S1",
        trechos_recuperados=["T01"],
        ferramentas_ativas=[],
        guardrail_acionado=False,
        duracao_segundos=1.0,
    )
    ex_rag_2 = ExecucaoCondicao(
        caso_id="RESP-02",
        condicao="rag_atual",
        pergunta="Pergunta 2",
        modelo="qwen2.5:3b",
        prompt_usuario="P2",
        contexto_fornecido="",
        resposta_completa={"evidence_summary": "S2"},
        resposta_texto_unificado="S2",
        trechos_recuperados=[],  # Falha na recuperação de evidências
        ferramentas_ativas=[],
        guardrail_acionado=False,
        duracao_segundos=1.0,
    )
    av1 = AvaliacaoCaso(
        caso_id="RESP-01",
        condicao="rag_atual",
        categoria="diretamente_respondivel",
        comportamento_esperado="responder",
        correcao_factual=1.0,
        completude=0.9,
        relevancia=1.0,
        seguranca_ressalvas=1.0,
        fidelidade_contexto=0.85,
        validade_citacoes=1.0,
        abstencao_adequada=True,
        erros_criticos_cometidos=[],
        fatos_atendidos=["F01"],
        fatos_ausentes=[],
        nota_geral_ponderada=0.95,
    )
    av2 = AvaliacaoCaso(
        caso_id="RESP-02",
        condicao="rag_atual",
        categoria="diretamente_respondivel",
        comportamento_esperado="responder",
        correcao_factual=0.6,
        completude=0.4,
        relevancia=0.6,
        seguranca_ressalvas=1.0,
        fidelidade_contexto=0.0,
        validade_citacoes=0.5,
        abstencao_adequada=True,
        erros_criticos_cometidos=[],
        fatos_atendidos=[],
        fatos_ausentes=["F02"],
        nota_geral_ponderada=0.55,
    )

    relatorio = gerar_relatorio_comparativo([av1, av2], [ex_rag_1, ex_rag_2])
    met_rag = relatorio["resumo_condicoes"]["rag_atual"]

    # Incerteza e desvio padrão
    assert "desvio_padrao" in met_rag
    assert "intervalo_confianca_95" in met_rag
    assert met_rag["desvio_padrao"] > 0
    assert len(met_rag["intervalo_confianca_95"]) == 2
    assert met_rag["intervalo_confianca_95"][0] <= met_rag["nota_geral_media"] <= met_rag["intervalo_confianca_95"][1]

    # Diagnóstico secundário de recuperação
    diag = relatorio["diagnostico_secundario_recuperacao"]
    assert diag["com_recuperacao_evidencias"]["n"] == 1
    assert diag["com_recuperacao_evidencias"]["nota_geral_media"] == 0.95
    assert diag["com_falha_de_recuperacao"]["n"] == 1
    assert diag["com_falha_de_recuperacao"]["nota_geral_media"] == 0.55


def test_resiliencia_execucao_rag_a_falhas(mocker):
    """Garante que falhas inesperadas na chamada RAG sejam capturadas sem derrubar o benchmark."""
    consultant = NutritionConsultantBaseline(
        enable_ollama=False,
        enable_taco_tool=False,
        enable_graph_engine=False,
    )
    mocker.patch.object(consultant, "consult", side_effect=RuntimeError("Falha simulada no motor RAG"))

    caso = carregar_golden_respostas(DEV_PATH)["casos"][0]
    execucao = executar_condicao_rag_atual(caso, consultant)

    assert execucao.condicao == "rag_atual"
    assert execucao.modelo == "erro-execucao-rag"
    assert "Falha simulada" in execucao.resposta_completa["evidence_summary"]


def test_langfuse_exige_opt_in_explicito(monkeypatch):
    """Credenciais no ambiente não devem enviar traces sem a flag explícita."""
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-lf-configurada")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-lf-configurada")
    assert obter_cliente_langfuse() is None
