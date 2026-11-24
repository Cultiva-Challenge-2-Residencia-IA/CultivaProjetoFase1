"""Reescrita de consulta, fusão RRF e Sincronizador (issue #99). Sem Ollama: o LLM é falso."""

from src.models.schemas import DocumentChunk, RetrievedChunk
from src.orquestrador.reescrita import Mensagem, reescrever
from src.orquestrador.roteamento import AREA_NUTRICAO, AREA_SAUDE_FISICA
from src.orquestrador.sincronizador import RespostaDeArea, sincronizar
from src.retrieval.fusao import fundir_rrf


def _chunk(cid: str, texto: str = "texto do trecho") -> RetrievedChunk:
    return RetrievedChunk(chunk=DocumentChunk(
        chunk_id=cid, doc_id=cid.split("-p")[0], title="Fonte", source_organization="Org",
        publication_year=2020, clinical_domain="x", evidence_level="GUIDELINE_CONSENSUS",
        section_path="Seção", raw_text=texto, contextualized_text=texto, pagina_pdf=1,
    ))


# Reescrita


def test_sem_llm_a_reescrita_usa_a_pergunta_original_e_as_regras():
    reescrita = reescrever("O que comer antes do treino?", historico=[], llm=None)
    assert reescrita.origem == "regras"
    assert reescrita.pergunta_completa == "O que comer antes do treino?"
    assert {s.area for s in reescrita.subperguntas} == {AREA_NUTRICAO, AREA_SAUDE_FISICA}
    assert all(s.trecho_hipotetico is None for s in reescrita.subperguntas)


def test_llm_resolve_continuacao_e_decompoe_em_subperguntas():
    def llm(_sistema, usuario):
        assert "hipertensão" in usuario  # o histórico chega ao LLM
        return {
            "pergunta_completa": "Qual exercício e qual alimentação ajudam quem tem hipertensão?",
            "subperguntas": [
                {"area": "saude_fisica", "pergunta": "Qual exercício ajuda quem tem hipertensão?",
                 "trecho_hipotetico": "Aerobic exercise lowers blood pressure in adults with hypertension."},
                {"area": "nutricao", "pergunta": "Qual alimentação ajuda quem tem hipertensão?",
                 "trecho_hipotetico": "O padrão DASH reduz a pressão arterial."},
            ],
        }

    historico = [Mensagem(papel="usuario", texto="Tenho hipertensão.", area=None)]
    reescrita = reescrever("E o que eu faço então?", historico=historico, llm=llm)
    assert reescrita.origem == "llm"
    assert reescrita.pergunta_completa.startswith("Qual exercício")
    por_area = {s.area: s for s in reescrita.subperguntas}
    assert por_area[AREA_SAUDE_FISICA].trecho_hipotetico.startswith("Aerobic")


def test_saida_invalida_do_llm_cai_nas_regras():
    reescrita = reescrever("Quantos minutos de caminhada por semana?", historico=[],
                           llm=lambda _s, _u: {"subperguntas": "não é lista"})
    assert reescrita.origem == "regras"
    assert [s.area for s in reescrita.subperguntas] == [AREA_SAUDE_FISICA]


def test_area_fora_das_permitidas_e_descartada():
    def llm(_s, _u):
        return {"pergunta_completa": "x", "subperguntas": [
            {"area": "estudos", "pergunta": "Como estudar?", "trecho_hipotetico": ""},
            {"area": "nutricao", "pergunta": "O que comer?", "trecho_hipotetico": "Coma frutas."},
        ]}

    reescrita = reescrever("Como estudar e o que comer?", historico=[], llm=llm)
    assert [s.area for s in reescrita.subperguntas] == [AREA_NUTRICAO]


# Fusão RRF


def test_trecho_achado_pelas_duas_consultas_sobe_na_fusao():
    a, b, c = _chunk("a-p001-01"), _chunk("b-p001-01"), _chunk("c-p001-01")
    fundidos = fundir_rrf([[a, b], [c, b]], top_k=3)
    assert [r.chunk.chunk_id for r in fundidos][0] == "b-p001-01"
    assert len(fundidos) == 3


def test_fusao_de_uma_lista_so_mantem_a_ordem():
    a, b = _chunk("a-p001-01"), _chunk("b-p001-01")
    assert [r.chunk.chunk_id for r in fundir_rrf([[a, b]], top_k=4)] == ["a-p001-01", "b-p001-01"]


# Sincronizador

NUTRI = RespostaDeArea(
    area=AREA_NUTRICAO,
    texto="O padrão DASH reduz a pressão arterial [T1].",
    trechos=[_chunk("dash-p010-01", "O padrão alimentar DASH reduz a pressão arterial em adultos.")],
)
FISICA = RespostaDeArea(
    area=AREA_SAUDE_FISICA,
    texto="Exercício aeróbico reduz a pressão arterial [T1].",
    trechos=[_chunk("who-p020-01", "Aerobic exercise reduces blood pressure in adults with hypertension.")],
)


def test_sem_llm_as_respostas_ficam_lado_a_lado_com_marcadores_renumerados():
    sinc = sincronizar("Como baixar a pressão?", [NUTRI, FISICA], llm=None)
    assert sinc.modo == "lado_a_lado"
    assert "[T1]" in sinc.texto and "[T2]" in sinc.texto  # o T1 da segunda área vira T2
    assert [t.chunk.chunk_id for t in sinc.trechos] == ["dash-p010-01", "who-p020-01"]


def test_llm_cruza_as_respostas_quando_as_citacoes_conferem():
    def llm(_s, _u):
        return {"evidence_summary": [
            {"frase": "Alimentação no padrão DASH e exercício aeróbico reduzem a pressão.", "trechos": [1, 2],
             "citacao": "O padrão alimentar DASH reduz a pressão arterial"},
        ]}

    sinc = sincronizar("Como baixar a pressão?", [NUTRI, FISICA], llm=llm)
    assert sinc.modo == "integrada"
    assert "[T1]" in sinc.texto


def test_llm_com_fato_sem_citacao_literal_cai_no_lado_a_lado():
    def llm(_s, _u):
        return {"evidence_summary": [
            {"frase": "Tomar remédio resolve.", "trechos": [1], "citacao": "remédio resolve a pressão sempre"},
        ]}

    sinc = sincronizar("Como baixar a pressão?", [NUTRI, FISICA], llm=llm)
    assert sinc.modo == "lado_a_lado"


def test_uma_resposta_so_passa_sem_sincronizar():
    sinc = sincronizar("Como baixar a pressão?", [NUTRI], llm=lambda _s, _u: None)
    assert sinc.modo == "area_unica"
    assert sinc.texto == NUTRI.texto
