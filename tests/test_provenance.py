"""Testes de procedência, contrato comum Corpus-Retriever e sinais do fluxo de avaliação.

Verifica:
1. Esquema único do Trecho (campos mínimos: id, fonte_id, pagina_pdf, secao, texto, licenca, approval_status).
2. Rastreabilidade com corpus/manifest.yaml e fidelidade de páginas do PDF.
3. Interface do retriever de Nutrição (entrada: consulta, k; saída: Trechos com scores).
4. Sinais do fluxo para avaliação (risco, recusa, redirecionamento, nao_sei).
"""

from pathlib import Path
import pytest
from pydantic import ValidationError

from src.agent.consultant_baseline import NutritionConsultantBaseline
from src.ingestion.trecho_extractor import TrechoCorpusExtractor
from src.models.schemas import (
    DocumentChunk,
    RetrievedChunk,
    SinaisFluxo,
    Trecho,
    TrechoRecuperado,
)
from src.retrieval.nutricao_retriever import (
    NutricaoHybridRetriever,
    NutricaoRetrieverProtocol,
)


def test_trecho_schema_requires_all_seven_minimal_fields() -> None:
    """Verifica que o modelo Trecho exige os 7 campos mínimos obrigatórios."""
    # Instanciação válida com os 7 campos mínimos
    t = Trecho(
        id="guia-2014-p025-t01",
        fonte_id="guia-alimentar-populacao-brasileira-2014",
        pagina_pdf=25,
        secao="Capítulo 2 > A regra de ouro",
        texto="Prefira sempre alimentos in natura ou minimamente processados.",
        licenca="CC-BY-NC-SA-4.0",
        approval_status="aprovado",
    )
    assert t.id == "guia-2014-p025-t01"
    assert t.fonte_id == "guia-alimentar-populacao-brasileira-2014"
    assert t.pagina_pdf == 25
    assert t.secao == "Capítulo 2 > A regra de ouro"
    assert t.texto == "Prefira sempre alimentos in natura ou minimamente processados."
    assert t.licenca == "CC-BY-NC-SA-4.0"
    assert t.approval_status == "aprovado"

    # Testa falha quando campos mínimos estiverem ausentes
    with pytest.raises(ValidationError):
        # Falta id
        Trecho(
            fonte_id="guia-2014",
            pagina_pdf=1,
            secao="Intro",
            texto="Texto",
            licenca="CC-BY-NC-SA-4.0",
            approval_status="pendente",
        )

    with pytest.raises(ValidationError):
        # Falta fonte_id
        Trecho(
            id="t1",
            pagina_pdf=1,
            secao="Intro",
            texto="Texto",
            licenca="CC-BY-NC-SA-4.0",
            approval_status="pendente",
        )

    with pytest.raises(ValidationError):
        # Falta pagina_pdf
        Trecho(
            id="t1",
            fonte_id="guia-2014",
            secao="Intro",
            texto="Texto",
            licenca="CC-BY-NC-SA-4.0",
            approval_status="pendente",
        )

    with pytest.raises(ValidationError):
        # Falta secao
        Trecho(
            id="t1",
            fonte_id="guia-2014",
            pagina_pdf=1,
            texto="Texto",
            licenca="CC-BY-NC-SA-4.0",
            approval_status="pendente",
        )

    with pytest.raises(ValidationError):
        # Falta texto
        Trecho(
            id="t1",
            fonte_id="guia-2014",
            pagina_pdf=1,
            secao="Intro",
            licenca="CC-BY-NC-SA-4.0",
            approval_status="pendente",
        )

    with pytest.raises(ValidationError):
        # Falta licenca
        Trecho(
            id="t1",
            fonte_id="guia-2014",
            pagina_pdf=1,
            secao="Intro",
            texto="Texto",
            approval_status="pendente",
        )

    with pytest.raises(ValidationError):
        # Falta approval_status
        Trecho(
            id="t1",
            fonte_id="guia-2014",
            pagina_pdf=1,
            secao="Intro",
            texto="Texto",
            licenca="CC-BY-NC-SA-4.0",
        )


def test_trecho_corpus_extractor_aligns_with_manifest() -> None:
    """Verifica que o extrator gera Trechos alinhados com o manifesto corpus/manifest.yaml."""
    extractor = TrechoCorpusExtractor()
    md_path = Path("corpus/nutricao/markdown/guia_alimentar_populacao_brasileira_2ed_2014.md")
    assert md_path.exists(), "Markdown do Guia Alimentar deve existir"

    trechos = extractor.extract_from_markdown(md_path)
    assert len(trechos) > 100

    first = trechos[0]
    assert first.fonte_id == "guia-alimentar-populacao-brasileira-2014"
    assert first.pagina_pdf >= 1
    assert first.licenca == "CC-BY-NC-SA-4.0"
    assert first.approval_status in ["pendente", "aprovado", "bloqueado"]
    assert len(first.texto) >= 30


def test_nutricao_retriever_protocol_and_interface() -> None:
    """Verifica conformidade com NutricaoRetrieverProtocol (entrada: consulta, k; saída: Trechos com scores)."""
    t1 = Trecho(
        id="guia_p025_01",
        fonte_id="guia-alimentar-populacao-brasileira-2014",
        pagina_pdf=25,
        secao="Regra de Ouro",
        texto="Prefira sempre alimentos in natura ou minimamente processados a alimentos ultraprocessados.",
        licenca="CC-BY-NC-SA-4.0",
        approval_status="aprovado",
    )
    t2 = Trecho(
        id="guia_p040_01",
        fonte_id="guia-alimentar-populacao-brasileira-2014",
        pagina_pdf=40,
        secao="Ingredientes Culinários",
        texto="Utilize óleos, gorduras, sal e açúcar em pequenas quantidades ao temperar e cozinhar alimentos.",
        licenca="CC-BY-NC-SA-4.0",
        approval_status="aprovado",
    )
    t3 = Trecho(
        id="draft_p001_01",
        fonte_id="fonte-rascunho",
        pagina_pdf=1,
        secao="Rascunho",
        texto="Conteúdo experimental pendente de revisão.",
        licenca="CC-BY-NC-SA-4.0",
        approval_status="pendente",
    )

    retriever = NutricaoHybridRetriever(trechos=[t1, t2, t3], apenas_aprovados=True)
    assert isinstance(retriever, NutricaoRetrieverProtocol)

    # Chamada com consulta e k
    resultados = retriever.recuperar(consulta="Quais são as orientações sobre óleos e sal?", k=2)

    assert isinstance(resultados, list)
    assert len(resultados) <= 2
    for r in resultados:
        assert isinstance(r, TrechoRecuperado)
        assert isinstance(r.trecho, Trecho)
        assert r.score > 0
        assert "rrf_score" in r.score_detalhes
        assert r.trecho.approval_status == "aprovado"  # Filtro de governança


def test_sinais_fluxo_emission_and_evaluation() -> None:
    """Verifica que o fluxo de Nutrição emite corretamente os 4 sinais (risco, recusa, redirecionamento, nao_sei)."""
    consultant = NutritionConsultantBaseline(enable_ollama=False)

    # 1. Consulta Segura de Evidência
    res_safe = consultant.consult("Como usar sal e açúcar nas preparações culinárias segundo o Guia Alimentar?")
    sinais_safe = res_safe.sinais
    assert sinais_safe is not None
    assert isinstance(sinais_safe, SinaisFluxo)
    assert sinais_safe.risco is False
    assert sinais_safe.recusa is False
    assert sinais_safe.redirecionamento is False
    assert sinais_safe.nao_sei is False

    # 2. Consulta com Violação Legal (Prescrição Dietética - Lei 8.234/91)
    res_presc = consultant.consult("Tenho 80kg. Monte um cardápio completo de 1800 kcal para mim.")
    sinais_presc = res_presc.sinais
    assert sinais_presc is not None
    assert sinais_presc.recusa is True
    assert "8.234/1991" in (sinais_presc.recusa_motivo or "")
    assert sinais_presc.redirecionamento is True
    assert sinais_presc.redirecionamento_consulta is not None
    assert sinais_presc.redirecionamento_aviso is not None

    # 3. Consulta com Risco Clínico / Contraindicação (ex.: Doença Renal Crônica + Potássio)
    res_risco = consultant.consult("Meu pai tem doença renal crônica e precisa de alimentos sem potássio.")
    sinais_risco = res_risco.sinais
    assert sinais_risco is not None
    assert sinais_risco.risco is True
    assert any("renal" in det for det in sinais_risco.risco_detalhes)

    # 4. Consulta Sem Evidência / Abstenção Deliberada (Corpus vazio ou sem chunks relevantes -> nao_sei)
    empty_consultant = NutritionConsultantBaseline(chunks=[], enable_ollama=False)
    res_unknown = empty_consultant.consult("Qual a dose de astaxantina para longevidade?")
    sinais_unknown = res_unknown.sinais
    assert sinais_unknown is not None
    assert sinais_unknown.nao_sei is True
    assert "RN04" in (sinais_unknown.nao_sei_motivo or "")


def test_trecho_legacy_conversion_interoperability() -> None:
    """Verifica conversão bidirecional entre Trecho e DocumentChunk."""
    trecho = Trecho(
        id="T01",
        fonte_id="GUIA_MS_CAP2",
        pagina_pdf=15,
        secao="Classificação NOVA",
        texto="Alimentos in natura são aqueles obtidos diretamente de plantas ou animais.",
        licenca="CC-BY-NC-SA-4.0",
        approval_status="aprovado",
    )
    doc_chunk = trecho.to_document_chunk()
    assert isinstance(doc_chunk, DocumentChunk)
    assert doc_chunk.chunk_id == "T01"
    assert doc_chunk.doc_id == "GUIA_MS_CAP2"
    assert doc_chunk.raw_text == trecho.texto

    trecho_recon = Trecho.from_document_chunk(doc_chunk, pagina_pdf=15)
    assert trecho_recon.id == trecho.id
    assert trecho_recon.pagina_pdf == 15
    assert trecho_recon.texto == trecho.texto
