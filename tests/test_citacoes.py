"""Citações por frase e bloqueio de resposta sem citação válida (issue #12)."""

from src.agent.llm_client import LocalLLMClient
from src.models.schemas import DocumentChunk, RetrievedChunk
from src.rag.verificador.citacoes import FRASE_SEM_BASE, dividir_frases, verificar_citacoes


def _campos(resumo, mecanismo="", protocolo=""):
    return {"evidence_summary": resumo, "physiological_mechanism": mecanismo, "protocol_findings": protocolo}


def test_frases_citadas_passam():
    v = verificar_citacoes(_campos("O Guia recomenda evitar ultraprocessados [T2]. Fibras ajudam o intestino [T1][T3]."), 4)
    assert v.valida and v.trechos_citados == [1, 2, 3] and v.frases == 2


def test_marcador_depois_do_ponto_conta_para_a_frase_anterior():
    assert dividir_frases("Frase um com quatro palavras. [T1] Frase dois sem marcador nenhum.") == [
        "Frase um com quatro palavras [T1].", "Frase dois sem marcador nenhum."]
    v = verificar_citacoes(_campos("Frase um com quatro palavras. [T1] Frase dois sem marcador nenhum."), 2)
    assert not v.valida and v.frases_sem_citacao == ["Frase dois sem marcador nenhum."]


def test_frase_sem_citacao_falha():
    v = verificar_citacoes(_campos("O Guia recomenda evitar ultraprocessados [T1].", "Isso reduz o risco de obesidade."), 4)
    assert not v.valida and "frase_sem_citacao:1" in v.problemas


def test_marcador_fora_do_intervalo_falha():
    v = verificar_citacoes(_campos("O Guia recomenda evitar ultraprocessados [T5]."), 4)
    assert not v.valida and v.marcadores_invalidos == ["[T5]"]


def test_grafo_e_taco_so_valem_com_a_ferramenta():
    texto = _campos("A aveia tem beta-glucana segundo o grafo [GRAFO][T1].")
    assert not verificar_citacoes(texto, 2).valida
    assert verificar_citacoes(texto, 2, tem_grafo=True).valida


def test_precisa_citar_ao_menos_um_trecho():
    v = verificar_citacoes(_campos("A aveia tem beta-glucana segundo o grafo [GRAFO]."), 2, tem_grafo=True)
    assert not v.valida and "nenhum_trecho_citado" in v.problemas


def test_frase_fixa_sem_base_e_frases_curtas_nao_exigem_citacao():
    v = verificar_citacoes(_campos("O Guia recomenda evitar ultraprocessados [T1].", FRASE_SEM_BASE, "Resumo:"), 1)
    assert v.valida and v.frases == 1


def test_resposta_vazia_falha():
    assert not verificar_citacoes(_campos(""), 2).valida


def _trechos(n=3):
    textos = [
        "O Guia recomenda evitar alimentos ultraprocessados. Eles têm muito açúcar e sódio. A ingestão aumenta o risco de obesidade.",
        "A fibra solúvel forma gel no intestino. O mecanismo envolve viscosidade e sequestro de ácidos biliares.",
        "Diretriz de consenso sobre o consumo de frutas. Protocolo populacional de 400 g/dia de frutas e hortaliças.",
    ]
    return [RetrievedChunk(chunk=DocumentChunk(
        chunk_id=f"doc{i}-p001-01", doc_id=f"doc{i}", title=f"Documento {i}", source_organization="Org",
        publication_year=2014, clinical_domain="nutricao", evidence_level="GUIDELINE_CONSENSUS",
        section_path="Seção", raw_text=t, contextualized_text=t, pagina_pdf=i + 1), score=1.0)
        for i, t in enumerate(textos[:n])]


def test_sintese_extrativa_so_produz_citacoes_validas():
    cliente = LocalLLMClient(enable_ollama=False)
    trechos = _trechos()
    sintese = cliente.synthesize_extractive_fallback("ultraprocessados", trechos)
    v = verificar_citacoes(sintese, len(trechos))
    assert v.valida, v.problemas
    assert v.trechos_citados and set(v.trechos_citados) <= {1, 2, 3}


def _cliente_com_llm(resposta):
    cliente = LocalLLMClient(enable_ollama=True, provider="ollama")
    cliente.is_ollama_available = lambda: True
    cliente._call_ollama_model = lambda modelo, prompt: resposta
    return cliente


def test_resposta_do_llm_sem_citacao_e_bloqueada_e_cai_na_extrativa():
    trechos = _trechos()
    resposta = {"evidence_summary": "Ultraprocessados fazem mal à saúde em qualquer quantidade.",
                "physiological_mechanism": "", "protocol_findings": "", "evidence_grade": "GRADE_A"}
    sintese, modelo = _cliente_com_llm(resposta).generate_structured_synthesis("ultraprocessados", trechos)
    assert modelo == "local_extractive_synthesis"
    assert sintese["_fundamentacao"]["status"] == "extrativa_apos_citacao_invalida"
    # Formato antigo, sem citação literal verificável: a frase sai e o resumo fica vazio (#67).
    assert any("resumo_sem_frase_com_citacao_literal" in p for p in sintese["_fundamentacao"]["problemas"])
    assert "qualquer quantidade" not in sintese["evidence_summary"]


def test_resposta_do_llm_citando_trecho_inexistente_e_bloqueada():
    # Citação que não existe em nenhuma fonte entregue: a frase sai, o resumo fica vazio e cai na extrativa.
    resposta = {"evidence_summary": [{"frase": "O Guia recomenda evitar ultraprocessados.", "trechos": [9],
                                      "citacao": "texto que não está em nenhum dos trechos entregues"}],
                "physiological_mechanism": [], "protocol_findings": []}
    cliente = _cliente_com_llm(resposta)
    sintese, modelo = cliente.generate_structured_synthesis("ultraprocessados", _trechos())
    assert modelo == "local_extractive_synthesis"
    assert cliente.ultimas_frases_removidas[0]["motivo"] == "citacao_literal_ausente_na_fonte"


def test_trecho_inexistente_com_citacao_verdadeira_tem_o_rotulo_corrigido():
    resposta = {"evidence_summary": [{"frase": "O Guia recomenda evitar ultraprocessados.", "trechos": [9],
                                      "citacao": "O Guia recomenda evitar alimentos ultraprocessados"}],
                "physiological_mechanism": [], "protocol_findings": []}
    cliente = _cliente_com_llm(resposta)
    sintese, modelo = cliente.generate_structured_synthesis("ultraprocessados", _trechos())
    assert modelo.startswith("ollama:") and "ultraprocessados [T1]." in sintese["evidence_summary"]
    assert sintese["_fundamentacao"]["rotulos_corrigidos"] == 1


def test_resposta_do_llm_citada_passa():
    resposta = {"evidence_summary": [{"frase": "O Guia recomenda evitar ultraprocessados.", "trechos": [1], "citacao": "O Guia recomenda evitar alimentos ultraprocessados"}],
                "physiological_mechanism": FRASE_SEM_BASE,
                "protocol_findings": [{"frase": "Há protocolo de 400 g/dia.", "trechos": [3], "citacao": "Protocolo populacional de 400 g/dia de frutas"}]}
    sintese, modelo = _cliente_com_llm(resposta).generate_structured_synthesis("ultraprocessados", _trechos())
    assert modelo.startswith("ollama:")
    assert sintese["_fundamentacao"]["status"] == "llm_citacoes_validas"


def test_prompt_numera_os_trechos_com_pagina():
    prompt = LocalLLMClient(enable_ollama=False)._build_user_prompt("pergunta", _trechos(2))
    assert "--- [T1] (doc0 |" in prompt and "| p. 1)" in prompt and "--- [T2] (doc1 |" in prompt


def test_llm_que_diz_nao_constar_vira_nao_sei_e_nao_extrativa():
    resposta = {c: FRASE_SEM_BASE for c in ("evidence_summary", "physiological_mechanism", "protocol_findings")}
    sintese, modelo = _cliente_com_llm(resposta).generate_structured_synthesis("como trocar um pneu?", _trechos())
    assert sintese["_fundamentacao"]["status"] == "llm_sem_base"
    assert "evidence_summary" not in sintese and modelo == "mensagem_fixa"


def test_prompt_pede_lista_de_frases_com_trechos():
    from src.agent.llm_client import SYSTEM_PROMPT_CONSULTANT
    assert '"evidence_summary": [{"frase": ' in SYSTEM_PROMPT_CONSULTANT and '"citacao": ' in SYSTEM_PROMPT_CONSULTANT
    assert f'"physiological_mechanism": [{{"frase": "{FRASE_SEM_BASE}"' in SYSTEM_PROMPT_CONSULTANT


def test_campos_so_vazios_nao_viram_nao_sei():
    # Revisão do #61: resposta incompleta não é abstenção; cai na checagem e no fallback.
    resposta = {"evidence_summary": "", "physiological_mechanism": "", "protocol_findings": ""}
    sintese, modelo = _cliente_com_llm(resposta).generate_structured_synthesis("ultraprocessados", _trechos())
    assert sintese["_fundamentacao"]["status"] == "extrativa_apos_citacao_invalida"
    assert modelo == "local_extractive_synthesis"


def test_cliente_guarda_a_checagem_que_decidiu_o_bloqueio():
    cliente = _cliente_com_llm({"evidence_summary": [{"frase": "Frase com marcador fora do intervalo.", "trechos": [9],
                                                      "citacao": "texto que não existe em nenhum trecho"}],
                                "physiological_mechanism": [], "protocol_findings": []})
    cliente.generate_structured_synthesis("ultraprocessados", _trechos())
    assert cliente.ultima_verificacao is not None and not cliente.ultima_verificacao.valida
    assert "resumo_sem_frase_com_citacao_literal" in cliente.ultima_verificacao.problemas


def test_taco_nao_e_confundido_com_trecho():
    # Bug achado na medição do prompt v2: "[TACO]" começa com "T" e quebrava int("ACO").
    v = verificar_citacoes(_campos("A aveia tem 9 g de fibra por 100 g [TACO][T1]."), 2, tem_taco=True)
    assert v.valida and v.trechos_citados == [1]
    v = verificar_citacoes(_campos("A aveia tem 9 g de fibra por 100 g [TACO]."), 2, tem_taco=True)
    assert not v.valida and "nenhum_trecho_citado" in v.problemas


# Formato estruturado (prompt v3): lista de {"frase", "trechos"}.

def test_formato_estruturado_vira_texto_com_marcadores():
    from src.rag.verificador.citacoes import normalizar_frases_citadas
    r = normalizar_frases_citadas({"evidence_summary": [
        {"frase": "O Guia recomenda evitar ultraprocessados.", "trechos": [2]},
        {"frase": "A aveia tem fibra", "trechos": ["1", "TACO"]},
    ], "protocol_findings": "texto antigo [T1]."})
    assert r["evidence_summary"] == "O Guia recomenda evitar ultraprocessados [T2]. A aveia tem fibra [T1][TACO]."
    assert r["protocol_findings"] == "texto antigo [T1]."


def test_resposta_estruturada_citada_passa():
    resposta = {"evidence_summary": [{"frase": "O Guia recomenda evitar ultraprocessados.", "trechos": [1], "citacao": "O Guia recomenda evitar alimentos ultraprocessados"}],
                "physiological_mechanism": [{"frase": FRASE_SEM_BASE, "trechos": []}],
                "protocol_findings": [{"frase": "Há um protocolo de 400 g/dia de frutas.", "trechos": [3], "citacao": "Protocolo populacional de 400 g/dia de frutas"}]}
    sintese, modelo = _cliente_com_llm(resposta).generate_structured_synthesis("ultraprocessados", _trechos())
    assert modelo.startswith("ollama:") and sintese["_fundamentacao"]["status"] == "llm_citacoes_validas"
    assert "ultraprocessados [T1]." in sintese["evidence_summary"]


def test_frase_estruturada_sem_trechos_ou_com_referencia_estranha_e_bloqueada():
    for refs in ([], ["fonte do guia"], [9]):
        resposta = {"evidence_summary": [{"frase": "O Guia recomenda evitar ultraprocessados.", "trechos": refs}],
                    "physiological_mechanism": [], "protocol_findings": []}
        sintese, modelo = _cliente_com_llm(resposta).generate_structured_synthesis("ultraprocessados", _trechos())
        assert modelo == "local_extractive_synthesis", refs


def test_estruturado_so_com_frase_fixa_vira_nao_sei():
    item = [{"frase": FRASE_SEM_BASE, "trechos": []}]
    resposta = {"evidence_summary": item, "physiological_mechanism": item, "protocol_findings": item}
    sintese, _ = _cliente_com_llm(resposta).generate_structured_synthesis("como trocar um pneu?", _trechos())
    assert sintese["_fundamentacao"]["status"] == "llm_sem_base"


# Citação literal (prompt v4, issue #67).

def test_frase_com_citacao_inventada_e_removida_e_as_outras_ficam():
    resposta = {"evidence_summary": [
        {"frase": "O Guia recomenda evitar ultraprocessados.", "trechos": [1], "citacao": "O Guia recomenda evitar alimentos ultraprocessados"},
        {"frase": "A piperina aumenta a curcumina em 20 vezes.", "trechos": [1],
         "citacao": "a piperina aumenta a biodisponibilidade da curcumina"},
    ], "physiological_mechanism": [{"frase": FRASE_SEM_BASE, "trechos": []}], "protocol_findings": []}
    cliente = _cliente_com_llm(resposta)
    sintese, modelo = cliente.generate_structured_synthesis("ultraprocessados", _trechos())
    assert modelo.startswith("ollama:") and sintese["_fundamentacao"]["frases_removidas"] == 1
    assert "piperina" not in sintese["evidence_summary"] and "ultraprocessados [T1]." in sintese["evidence_summary"]


def test_citacao_curta_ou_alterada_nao_vale_e_caixa_nao_conta():
    from src.rag.verificador.citacoes import citacao_literal_valida
    assert not citacao_literal_valida("evitar alimentos", ["O Guia recomenda evitar alimentos ultraprocessados."])
    # Caixa e hifenização de quebra de linha não contam (critérios da #67).
    assert citacao_literal_valida("Recomenda EVITAR alimentos ultra-\nprocessados", ["O Guia recomenda evitar alimentos ultraprocessados."])
    # Mas trocar uma palavra invalida a citação.
    assert not citacao_literal_valida("recomenda evitar todos os alimentos", ["O Guia recomenda evitar alimentos ultraprocessados."])


def test_citacao_de_outra_fonte_nao_vale_para_a_fonte_citada():
    from src.rag.verificador.citacoes import filtrar_citacoes_literais
    r, ajustes = filtrar_citacoes_literais(
        {"evidence_summary": [{"frase": "x y z w.", "trechos": [2], "citacao": "O Guia recomenda evitar alimentos"}]},
        {"T1": "O Guia recomenda evitar alimentos ultraprocessados.", "T2": "A fibra solúvel forma gel."})
    # A citação está no T1, mas a frase cita o T2: a frase fica, com o rótulo trocado para o T1.
    assert [a["motivo"] for a in ajustes] == ["rotulo_corrigido"]
    assert r["evidence_summary"][0]["trechos"] == [1]


def test_citacao_ausente_de_todas_as_fontes_remove_a_frase():
    from src.rag.verificador.citacoes import filtrar_citacoes_literais
    r, ajustes = filtrar_citacoes_literais(
        {"evidence_summary": [{"frase": "x y z w.", "trechos": [1], "citacao": "o Guia proíbe todos os ultraprocessados"}]},
        {"T1": "O Guia recomenda evitar alimentos ultraprocessados.", "T2": "A fibra solúvel forma gel."})
    assert r["evidence_summary"] == []
    assert [a["motivo"] for a in ajustes] == ["citacao_literal_ausente_na_fonte"]


def test_citacao_verdadeira_com_rotulo_errado_fica_com_o_rotulo_corrigido():
    from src.rag.verificador.citacoes import filtrar_citacoes_literais
    textos = {"T1": "A fibra solúvel forma gel.", "TACO": "Feijão, carioca, cozido: Proteína (g): 4.78"}
    r, ajustes = filtrar_citacoes_literais(
        {"evidence_summary": [{"frase": "O feijão tem 4,78 g de proteína.", "trechos": [4],
                               "citacao": "Feijão, carioca, cozido: Proteína (g): 4.78"}]}, textos)
    assert r["evidence_summary"][0]["trechos"] == ["TACO"]
    assert ajustes[0]["motivo"] == "rotulo_corrigido"


def test_numero_colado_a_unidade_conta_como_igual():
    from src.rag.verificador.citacoes import citacao_literal_valida
    assert citacao_literal_valida("Recebem este nome por fornecer < 800kcal por dia", ["recebem este nome por fornecer < 800 kcal por dia."])


def test_frases_removidas_ficam_no_estado_da_thread():
    import threading

    resposta = {"evidence_summary": [{"frase": "O Guia proíbe ultraprocessados.", "trechos": [1],
                                      "citacao": "o Guia proíbe todos os ultraprocessados"}],
                "physiological_mechanism": [], "protocol_findings": []}
    cliente = _cliente_com_llm(resposta)
    cliente.generate_structured_synthesis("ultraprocessados", _trechos())
    assert len(cliente.ultimas_frases_removidas) == 1
    vistos = {}

    def outra_thread():
        vistos["removidas"] = cliente.ultimas_frases_removidas
        vistos["aceita"] = cliente.ultima_resposta_aceita

    t = threading.Thread(target=outra_thread)
    t.start()
    t.join()
    assert vistos == {"removidas": [], "aceita": None}
