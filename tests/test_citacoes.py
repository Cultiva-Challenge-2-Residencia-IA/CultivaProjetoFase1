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
    assert any("frase_sem_citacao" in p for p in sintese["_fundamentacao"]["problemas"])
    assert "qualquer quantidade" not in sintese["evidence_summary"]


def test_resposta_do_llm_citando_trecho_inexistente_e_bloqueada():
    resposta = {"evidence_summary": "O Guia recomenda evitar ultraprocessados [T9].",
                "physiological_mechanism": "", "protocol_findings": ""}
    sintese, modelo = _cliente_com_llm(resposta).generate_structured_synthesis("ultraprocessados", _trechos())
    assert modelo == "local_extractive_synthesis"
    assert any("[T9]" in p for p in sintese["_fundamentacao"]["problemas"])


def test_resposta_do_llm_citada_passa():
    resposta = {"evidence_summary": "O Guia recomenda evitar ultraprocessados [T1].",
                "physiological_mechanism": FRASE_SEM_BASE, "protocol_findings": "Há protocolo de 400 g/dia [T3]."}
    sintese, modelo = _cliente_com_llm(resposta).generate_structured_synthesis("ultraprocessados", _trechos())
    assert modelo.startswith("ollama:")
    assert sintese["_fundamentacao"]["status"] == "llm_citacoes_validas"


def test_prompt_numera_os_trechos_com_pagina():
    prompt = LocalLLMClient(enable_ollama=False)._build_user_prompt("pergunta", _trechos(2))
    assert "--- [T1] (doc0 |" in prompt and "| p. 1)" in prompt and "--- [T2] (doc1 |" in prompt
