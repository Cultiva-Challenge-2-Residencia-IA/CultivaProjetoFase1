"""Script de avaliação da comparação de modelos locais (issue #55), sem Ollama nem Groq."""

import json

import pytest

from src.evaluation.modelo_local import config, ferramentas, juiz
from src.evaluation.modelo_local.entradas import carregar
from src.evaluation.modelo_local.geracao import validar_esquema
from src.evaluation.modelo_local.metricas import bootstrap_pareado, imperativos_prescritivos, rouge_l

SAIDA_OK = {"evidence_summary": "a", "physiological_mechanism": "b", "protocol_findings": "c",
            "food_sources_or_compounds": ["feijão"], "evidence_grade": "GRADE_B"}


def test_esquema_exige_os_cinco_campos_nos_tipos_certos():
    assert validar_esquema(json.dumps(SAIDA_OK)) == {"json_valido": True, "esquema_valido": True, "saida": SAIDA_OK}
    incompleta = {**SAIDA_OK, "food_sources_or_compounds": "feijão"}
    assert validar_esquema(json.dumps(incompleta))["esquema_valido"] is False
    assert validar_esquema("{não é json")["json_valido"] is False


def test_rouge_l_mede_a_resposta_contra_a_fonte():
    fonte = "o feijao e fonte de ferro nao heme e a vitamina c aumenta a absorcao"
    assert rouge_l("feijão é fonte de ferro", fonte)["rouge_l_precisao"] == 1.0
    assert rouge_l("chocolate cura gripe", fonte)["rouge_l_precisao"] == 0.0


def test_imperativos_do_guardrail_de_saida_contam_como_prescricao():
    assert imperativos_prescritivos("Tome 2 cápsulas por dia.")
    assert not imperativos_prescritivos("As diretrizes indicam 2,4 mcg/dia de B12 para adultos.")


def test_bootstrap_pareado_separa_diferenca_real_de_empate():
    a = {str(i): 1.0 for i in range(30)}
    b = {str(i): 0.0 for i in range(30)}
    assert bootstrap_pareado(a, b)["significativa"] is True
    ruido = {str(i): float(i % 2) for i in range(30)}
    espelho = {str(i): float((i + 1) % 2) for i in range(30)}
    assert bootstrap_pareado(ruido, espelho)["significativa"] is False
    assert bootstrap_pareado({"x": 1.0}, {"x": 0.0}) is None


@pytest.mark.parametrize("chamadas, esperado", [
    ([{"ferramenta": "consultar_taco", "argumentos": {"alimento": "Feijão carioca", "nutriente": "ferro"}}],
     {"escolha_correta": 1.0, "argumentos_corretos": 1.0}),
    ([{"ferramenta": "consultar_taco", "argumentos": {"alimento": "arroz", "nutriente": "ferro"}}],
     {"escolha_correta": 1.0, "argumentos_corretos": 0.0}),
    ([{"ferramenta": "buscar_evidencias", "argumentos": {"pergunta": "ferro no feijão"}}],
     {"escolha_correta": 0.0, "argumentos_corretos": 0.0}),
])
def test_pontuacao_de_ferramentas(chamadas, esperado):
    caso = next(c for c in ferramentas.carregar_casos() if c["id"] == "FER-TACO-01")
    assert ferramentas.pontuar(caso, {"chamadas": chamadas}) == esperado


def test_registro_de_refeicao_aceita_enum_com_sublinhado():
    caso = next(c for c in ferramentas.carregar_casos() if c["id"] == "FER-REG-02")
    chamada = {"ferramenta": "propor_registro_refeicao",
               "argumentos": json.dumps({"refeicao": "cafe_da_manha", "descricao": "pão com ovo"})}
    assert ferramentas.pontuar(caso, {"chamadas": [chamada]})["argumentos_corretos"] == 1.0


def test_pedido_de_dieta_nao_pode_virar_registro():
    caso = next(c for c in ferramentas.carregar_casos() if c["id"] == "FER-NAO-04")
    registro = [{"ferramenta": "propor_registro_refeicao", "argumentos": {}}]
    assert ferramentas.pontuar(caso, {"chamadas": registro})["escolha_correta"] == 0.0
    busca = [{"ferramenta": "buscar_evidencias", "argumentos": {"pergunta": "dieta"}}]
    assert ferramentas.pontuar(caso, {"chamadas": busca})["escolha_correta"] == 1.0


def test_casos_de_ferramenta_tem_ids_unicos_e_ferramentas_conhecidas():
    casos = ferramentas.carregar_casos()
    assert len({c["id"] for c in casos}) == len(casos)
    nomes = {f["function"]["name"] for f in ferramentas.FERRAMENTAS}
    assert all(e["ferramenta"] in nomes for c in casos for e in c["esperado"])


def test_juiz_resume_fidelidade_e_prescricao():
    resumo = juiz._resumir({"afirmacoes": [{"afirmacao": "a", "veredito": "sustentada"},
                                           {"afirmacao": "b", "veredito": "nao_sustentada"}],
                            "prescricao_individual": False})
    assert resumo["fidelidade"] == 0.5 and resumo["n_afirmacoes"] == 2
    assert juiz._resumir({"afirmacoes": []})["fidelidade"] is None


def test_validacao_do_juiz_tem_os_tres_tipos_por_caso():
    dados = juiz.montar_validacao(carregar(), quantidade=4)
    tipos = [i["tipo"] for i in dados["itens"]]
    assert tipos.count("fiel") == tipos.count("inventada") == tipos.count("prescricao") >= 3
    inventada = next(i for i in dados["itens"] if i["tipo"] == "inventada")
    assert all(inv in inventada["resposta"] for inv in inventada["invencoes"])


def test_item_de_validacao_correto():
    fiel = {"tipo": "fiel"}
    ok = {"afirmacoes": [{"veredito": "sustentada"}], "fidelidade": 1.0, "prescricao_individual": False}
    assert juiz.item_correto(fiel, ok)
    assert not juiz.item_correto({"tipo": "inventada"}, ok)
    assert juiz.item_correto({"tipo": "prescricao"}, {**ok, "prescricao_individual": True})


def test_juiz_externo_exige_liberacao(monkeypatch):
    monkeypatch.setattr(juiz, "ALLOW_EXTERNAL_LLM", False)
    monkeypatch.delenv("ALLOW_EXTERNAL_LLM", raising=False)
    with pytest.raises(juiz.JuizIndisponivel):
        juiz.Juiz(chave="x")


def test_entradas_congeladas_cobrem_os_tipos_e_trazem_o_prompt():
    casos = carregar()
    assert len({c["id"] for c in casos}) == len(casos) >= 80
    assert {"recuperacao", "prescricao", "dentro"} <= {c["tipo"] for c in casos}
    assert all("<dados_de_referencia>" in c["user_prompt"] for c in casos)


def test_candidatos_incluem_a_referencia_atual():
    assert config.CANDIDATOS[0] == "qwen2.5:7b"
    assert len(set(config.CANDIDATOS)) == len(config.CANDIDATOS)


def _resultado(fid, cob, lat, passa=True):
    casos = [str(i) for i in range(30)]
    return {"passa": passa, "fidelidade_semente_1": sum(fid) / len(fid), "cobertura_termos": sum(cob) / len(cob),
            "latencia_p50": lat, "info": {"memoria_total_bytes": 5e9},
            "_fidelidade_s1": dict(zip(casos, fid)), "_por_caso": {"cobertura_termos": dict(zip(casos, cob))}}


def test_classificacao_desempata_pela_latencia_e_elimina_quem_falha():
    from src.evaluation.modelo_local.relatorio import classificar

    alto = [1.0] * 30
    quase = [1.0] * 29 + [0.0]
    baixo = [0.0] * 30
    resultados = {
        "lento": _resultado(alto, alto, 9.0),
        "rapido": _resultado(quase, alto, 3.0),
        "fraco": _resultado(baixo, alto, 1.0),
        "inseguro": _resultado(alto, alto, 1.0, passa=False),
    }
    ordem, empate = classificar(resultados)
    assert ordem == ["rapido", "lento", "fraco"]
    assert set(empate) == {"lento", "rapido"}


def test_amostra_do_juiz_inclui_toda_a_seguranca_e_e_estavel():
    from src.evaluation.modelo_local.metricas import TIPOS_DE_SEGURANCA

    casos = carregar()
    amostra = juiz.amostra_do_juiz(casos, tamanho=30)
    seguranca = {c["id"] for c in casos if c["tipo"] in TIPOS_DE_SEGURANCA}
    assert seguranca <= set(amostra)
    assert len(amostra) == len(set(amostra)) == len(seguranca) + 30
    assert amostra == juiz.amostra_do_juiz(casos, tamanho=30)


def test_kappa_e_concordancia_binaria():
    from src.evaluation.modelo_local.cego import kappa

    assert kappa([True, False, True, False], [True, False, True, False]) == 1.0
    assert kappa([True, True, False, False], [False, False, True, True]) == -1.0
    assert kappa([], []) is None


def test_lotes_cegos_escondem_o_modelo_e_aceitam_so_quem_acerta_os_controles(tmp_path, monkeypatch):
    from src.evaluation.modelo_local import cego

    monkeypatch.setattr(cego, "LOTES_DIR", tmp_path / "lotes")
    monkeypatch.setattr(cego, "CHAVE_DIR", tmp_path / "chave")
    monkeypatch.setattr(cego, "TAMANHO_LOTE", 2)
    itens = [{"origem": {"tipo": "candidato", "modelo": f"m{i}:7b", "caso": f"C{i}", "semente": 1},
              "pergunta": "p", "contexto": "c", "resposta": f"r{i}"} for i in range(3)]
    monkeypatch.setattr(cego, "candidatos", lambda modelos, sementes: [dict(x) for x in itens])
    resumo = cego.exportar("s1", ["m0:7b"], [1])
    assert resumo["lotes"] == 2 and resumo["controles_por_lote"] == 3
    texto = (tmp_path / "lotes" / "s1" / "lote_01.json").read_text(encoding="utf-8")
    assert "m0:7b" not in texto and "m1:7b" not in texto
    assert "origem" not in texto and "tipo_controle" not in texto

    chave = json.loads((tmp_path / "chave" / "s1.json").read_text(encoding="utf-8"))
    validacao = json.loads(config.JUIZ_VALIDACAO_PATH.read_text(encoding="utf-8"))["itens"]
    destinos = {}
    monkeypatch.setattr(cego, "arquivo_do_modelo", lambda m, pasta="geracoes": destinos.setdefault(
        (m, pasta), tmp_path / pasta / f"{m.replace(':', '_')}.jsonl"))
    for nome, mapa in chave["lotes"].items():
        resposta = {}
        for i, origem in mapa.items():
            correto = origem["tipo"] != "controle" or nome == "lote_01"
            tipo = validacao[origem["indice"]]["tipo"] if origem["tipo"] == "controle" else "fiel"
            sustentada = {"afirmacao": "a", "veredito": "sustentada"}
            inventada = {"afirmacao": "b", "veredito": "nao_sustentada"}
            afirmacoes = [sustentada] if tipo == "fiel" else [sustentada, inventada]
            resposta[i] = {"afirmacoes": afirmacoes if correto else [inventada],
                           "prescricao_individual": correto and tipo == "prescricao"}
        (tmp_path / "lotes" / "s1" / f"{nome}.resposta.json").write_text(json.dumps(resposta), encoding="utf-8")
    resultado = cego.importar("s1")
    assert resultado["aceitos"] == ["lote_01"] and "lote_02" in resultado["rejeitados"]
    assert sum(resultado["julgamentos_importados"].values()) == 2
