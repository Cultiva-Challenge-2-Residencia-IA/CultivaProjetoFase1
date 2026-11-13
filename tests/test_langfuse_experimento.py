from types import SimpleNamespace

import pytest

from src.evaluation import langfuse_experimento as exp
from src.evaluation.benchmark_v2 import carregar_casos


def _caso(caso_id="V2-X-01", split="dev"):
    return {
        "id": caso_id,
        "tipo": "recuperacao",
        "split": split,
        "pergunta": "Pergunta?",
        "comportamento_esperado": "responder",
    }


def test_item_do_caso_guarda_o_caso_inteiro_como_saida_esperada():
    caso = _caso()
    item = exp.item_do_caso(caso)
    assert item["id"] == "golden-v2-V2-X-01"
    assert item["input"] == {"pergunta": "Pergunta?"}
    assert item["expected_output"] is caso
    assert item["metadata"]["split"] == "dev"


def test_ids_dos_itens_sao_unicos_no_golden_set():
    ids = [exp.id_do_item(c["id"]) for c in carregar_casos()]
    assert len(ids) == len(set(ids))


def test_avaliacoes_do_caso_usam_os_nomes_do_relatorio():
    avaliacao = {"id": "V2-X-01", "rr_trecho": 0.5, "acerto_trecho": 1.0, "trechos_recuperados": ["a"]}
    nomes = {a.name: a.value for a in exp.avaliacoes_do_caso(avaliacao)}
    assert nomes == {"mrr_trecho": 0.5, "acerto_trecho_at_k": 1.0}


def test_avaliacoes_da_execucao_sao_as_medias_do_benchmark():
    resultados = [{"rr_trecho": 1.0, "prescricao_detectada": 0.0}, {"rr_trecho": 0.5}]
    nomes = {a.name: (a.value, a.comment) for a in exp.avaliacoes_da_execucao(resultados)}
    assert nomes == {"mrr_trecho": (0.75, "n=2"), "guardrail_recall_prescricao": (0.0, "n=1")}


class _ClienteFalso:
    def __init__(self, itens_existentes):
        self.itens = {i.id: i for i in itens_existentes}
        self.criados = []

    def get_dataset(self, nome):
        return SimpleNamespace(items=list(self.itens.values()))

    def create_dataset(self, **_):
        raise AssertionError("o dataset já existe")

    def create_dataset_item(self, *, dataset_name, id, status="ACTIVE", **kwargs):
        self.criados.append((id, status))
        self.itens[id] = SimpleNamespace(id=id, status=status, **kwargs)


def test_sincronizar_dataset_atualiza_casos_e_arquiva_os_removidos():
    antigo = SimpleNamespace(id="golden-v2-REMOVIDO", status="ACTIVE", input={}, expected_output={}, metadata={})
    cliente = _ClienteFalso([antigo])
    exp.sincronizar_dataset(cliente, [_caso("A"), _caso("B")])
    assert ("golden-v2-A", "ACTIVE") in cliente.criados
    assert ("golden-v2-B", "ACTIVE") in cliente.criados
    assert ("golden-v2-REMOVIDO", "ARCHIVED") in cliente.criados


def test_executar_exige_langfuse_ligado():
    with pytest.raises(SystemExit, match="CULTIVA_LANGFUSE"):
        exp.executar(enable_llm=False)


def test_filtrar_por_componentes_remove_metricas_dos_componentes_desligados():
    avaliacao = {"rr_trecho": 1.0, "citacoes_validas": 1.0, "taco_correto": 0.0,
                 "cadeia_encontrada": 1.0, "cobertura_termos": 0.5, "guardrail_correto": 1.0}
    puro = exp.filtrar_por_componentes(avaliacao, exp.CONFIGURACOES["llm-puro"])
    # A citação é métrica de resposta: fica em todas as configurações.
    assert puro == {"citacoes_validas": 1.0, "cobertura_termos": 0.5, "guardrail_correto": 1.0}
    rag = exp.filtrar_por_componentes(avaliacao, exp.CONFIGURACOES["llm-rag"])
    assert "rr_trecho" in rag and "taco_correto" not in rag and "cadeia_encontrada" not in rag
    assert exp.filtrar_por_componentes(avaliacao, exp.CONFIGURACOES["completo"]) == avaliacao


def test_metricas_de_texto_separam_resposta_final_e_texto_do_llm():
    caso = {"geracao": {"termos_obrigatorios": [["fibra"], ["intestino"]]}}
    final = {"evidence_summary": "Fibra ajuda o intestino.", "physiological_mechanism": "", "protocol_findings": ""}
    llm = {"evidence_summary": "Fibra ajuda.", "physiological_mechanism": "", "protocol_findings": ""}
    metricas = exp.metricas_de_texto(caso, final, llm)
    assert metricas["cobertura_termos_llm"] == 0.5
    assert metricas["tamanho_resposta"] > metricas["tamanho_resposta_llm"]
    assert exp.metricas_de_texto(caso, final, None) == {"tamanho_resposta": metricas["tamanho_resposta"]}


def test_llm_puro_exige_llm():
    with pytest.raises(SystemExit, match="llm-puro"):
        exp.executar(enable_llm=False, nome_config="llm-puro")


class _ConsultorFalso:
    """Devolve as respostas na ordem dada, simulando falhas do modelo principal."""

    def __init__(self, modelos):
        self.modelos = list(modelos)
        self.chamadas = 0
        self.llm_client = SimpleNamespace(ultima_sintese_llm=None)

    def consult(self, pergunta, top_k):
        modelo = self.modelos[min(self.chamadas, len(self.modelos) - 1)]
        self.chamadas += 1
        self.llm_client.ultima_sintese_llm = {"evidence_summary": "fibra"} if modelo.startswith("groq") else None
        return SimpleNamespace(
            model_used=modelo, guardrail_triggered=False, evidence_summary="fibra",
            physiological_mechanism="", protocol_findings="", citations=[], retrieved_chunks=[],
            graph_paths=[], taco_records=[],
            model_dump=lambda: {"evidence_summary": "fibra"},
        )


def _item():
    caso = _caso()
    caso["geracao"] = {"termos_obrigatorios": [["fibra"]]}
    return {"expected_output": caso}


def test_tarefa_tenta_de_novo_ate_o_modelo_fixado_responder():
    consultor = _ConsultorFalso(["local_extractive_synthesis", "groq:principal"])
    tarefa = exp.criar_tarefa(consultor, 4, exp.CONFIGURACOES["llm-puro"], "groq:principal", esperas=(0, 0))
    saida = tarefa(item=_item())
    assert consultor.chamadas == 2
    assert saida["avaliacao"]["llm_respondeu"] == 1.0
    assert saida["avaliacao"]["cobertura_termos_llm"] == 1.0


def test_tarefa_tira_metricas_de_texto_quando_o_modelo_fixado_nao_responde():
    consultor = _ConsultorFalso(["groq:reserva"])
    tarefa = exp.criar_tarefa(consultor, 4, exp.CONFIGURACOES["llm-puro"], "groq:principal", esperas=(0, 0))
    avaliacao = tarefa(item=_item())["avaliacao"]
    assert consultor.chamadas == 3
    assert avaliacao["llm_respondeu"] == 0.0
    assert not exp.CAMPOS_DEPENDENTES_DO_LLM & set(avaliacao)
    assert "guardrail_correto" in avaliacao


def test_fixar_modelo_desliga_os_reservas():
    cliente = SimpleNamespace(provider="groq", groq_model="principal", groq_fallback_model="reserva",
                              enable_ollama=True)
    assert exp.fixar_modelo(cliente) == "groq:principal"
    assert cliente.groq_fallback_model == "" and cliente.enable_ollama is False


def test_taco_valor_no_texto_exige_alimento_e_valor_dentro_da_tolerancia():
    spec = {"alimento": "Feijão, carioca, cozido", "campo": "protein_g", "valor": 4.8, "tolerancia": 0.1}
    assert exp.taco_valor_no_texto(spec, "o feijao carioca tem 4,8 g de proteina") == 1.0
    assert exp.taco_valor_no_texto(spec, "o feijao tem 4.85 g") == 1.0
    assert exp.taco_valor_no_texto(spec, "o feijao tem 6 g de proteina") == 0.0
    assert exp.taco_valor_no_texto(spec, "a lentilha tem 4,8 g") == 0.0


def test_metricas_de_resposta_olham_o_texto_e_nao_os_componentes():
    caso = {
        "grafo": {"cadeia_esperada": [["feijao"], ["ferro nao-heme"], ["vitamina c"]]},
        "taco": {"alimento": "Banana, prata, crua", "campo": "potassium_mg", "valor": 358, "tolerancia": 1},
    }
    final = {"evidence_summary": "Feijão tem ferro não-heme; a banana tem 358 mg de potássio.",
             "physiological_mechanism": "", "protocol_findings": ""}
    llm = {"evidence_summary": "Feijão e vitamina C.", "physiological_mechanism": "", "protocol_findings": ""}
    metricas = exp.metricas_de_texto(caso, final, llm)
    assert metricas["grafo_cadeia_no_texto"] == pytest.approx(2 / 3)
    assert metricas["grafo_cadeia_no_texto_llm"] == pytest.approx(2 / 3)
    assert metricas["taco_valor_no_texto"] == 1.0
    assert metricas["taco_valor_no_texto_llm"] == 0.0


def test_metricas_comuns_saem_iguais_no_llm_puro_e_no_completo():
    """A comparação da ablação só faz sentido se as métricas de resposta forem as mesmas."""
    avaliacao = {campo: 1.0 for campo in exp.NOME_DA_METRICA}
    nomes = {}
    for config_nome in ("llm-puro", "completo"):
        filtrada = exp.filtrar_por_componentes(avaliacao, exp.CONFIGURACOES[config_nome])
        nomes[config_nome] = {a.name for a in exp.avaliacoes_do_caso(filtrada)}
    assert set(exp.METRICAS_COMUNS) <= nomes["llm-puro"]
    assert nomes["llm-puro"] == set(exp.METRICAS_COMUNS)
    assert set(exp.METRICAS_COMUNS) < nomes["completo"]


def test_metricas_comuns_sao_metricas_conhecidas():
    assert set(exp.METRICAS_COMUNS) <= set(exp.TODAS_AS_METRICAS)
