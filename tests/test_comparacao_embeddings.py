"""Embeddings por modelo e calibração do "não sei" da comparação de embeddings (issue #15).

Não carregam modelo: cobrem prefixos, impressão digital, preparo do texto e a regra do limiar.
"""

import hashlib

from src.evaluation.comparacao_embeddings import calibrar_limiar, resumo_abstencao
from src.models.schemas import DocumentChunk
from src.retrieval.hybrid_retriever import expand_clinical_synonyms, expandir_sinonimos
from src.retrieval.vector_store import configuracao_hnsw, impressao_digital, prefixos_do_modelo

MINILM = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
E5 = "intfloat/multilingual-e5-large"


def _chunk(cid: str, texto: str) -> DocumentChunk:
    return DocumentChunk(
        chunk_id=cid, doc_id="fonte", title="Título", source_organization="Org", publication_year=2020,
        clinical_domain="nutricao", evidence_level="GUIDELINE_CONSENSUS", section_path="Seção",
        raw_text=texto, contextualized_text=texto,
    )


def test_e5_usa_os_prefixos_de_consulta_e_documento():
    assert prefixos_do_modelo(E5) == ("query: ", "passage: ")
    assert prefixos_do_modelo(MINILM) == ("", "")


def test_impressao_digital_do_modelo_atual_nao_muda():
    """A coleção já construída com o MiniLM continua com o mesmo nome depois da #15."""
    chunks = [_chunk("a", "Arroz e feijão"), _chunk("b", "Frutas in natura")]
    h = hashlib.sha256(MINILM.encode())
    h.update(repr(sorted(configuracao_hnsw().items())).encode())
    for c in chunks:
        h.update(c.chunk_id.encode())
        h.update(c.contextualized_text.encode())
    assert impressao_digital(chunks, MINILM) == h.hexdigest()


def test_impressao_digital_muda_com_modelo_e_preparo_do_texto():
    chunks = [_chunk("a", "Arroz e feijão")]
    base = impressao_digital(chunks, MINILM)
    assert impressao_digital(chunks, E5) != base
    assert impressao_digital(chunks, MINILM, normalizar_texto=False) != base


def test_texto_original_preserva_acentos_e_acrescenta_sinonimos():
    texto = "Açúcar no sangue alto"
    assert expandir_sinonimos(texto) == expand_clinical_synonyms(texto)
    original = expandir_sinonimos(texto, normalizar=False)
    assert original.startswith("Açúcar no sangue alto ")
    assert "glicemia" in original


def _medida(mid, pergunta, sim, tipo, esperado, split="dev", origem="abstencao"):
    return {"id": mid, "pergunta": pergunta, "similaridade": sim, "tipo": tipo, "esperado": esperado,
            "split": split, "origem": origem}


def test_calibracao_maximiza_fora_de_nutricao_sem_recusar_pergunta_boa():
    medidas = [
        # Pergunta boa sem termo de Nutrição: o limiar precisa ficar abaixo de 0,50.
        _medida("D1", "Qual a regra de ouro do guia?", 0.50, "dentro", "responder"),
        # Com termo de Nutrição nunca é recusada, por menor que seja o cosseno.
        _medida("D2", "Jejum intermitente funciona?", 0.10, "dentro", "responder"),
        _medida("F1", "Como trocar o pneu?", 0.30, "fora_de_nutricao", "nao_sei"),
        _medida("F2", "Como declarar imposto?", 0.45, "fora_de_nutricao", "nao_sei"),
        _medida("F3", "Como tirar passaporte?", 0.60, "fora_de_nutricao", "nao_sei"),
        # O test não entra na calibração.
        _medida("T1", "Qual a capital da França?", 0.40, "fora_de_nutricao", "nao_sei", split="test"),
    ]
    cal = calibrar_limiar(medidas)
    assert 0.45 < cal["limiar"] <= 0.50
    assert cal["fora_de_nutricao_dev"] == 2
    assert cal["menor_cosseno_responder_sem_termo_dev"] == 0.50
    resumo = resumo_abstencao(medidas, cal["limiar"])
    assert resumo["recusas_indevidas"] == []
    assert resumo["fora_de_nutricao_respondidos"] == ["F3"]
    assert resumo["test"]["nao_sei_fora_de_nutricao"] == 1.0


def test_pergunta_parada_em_portao_anterior_nao_conta_como_nao_sei():
    medidas = [_medida("R1", "Quero sumir", None, "fora_de_nutricao", "nao_sei")]
    assert resumo_abstencao(medidas, 0.9)["fora_de_nutricao_respondidos"] == ["R1"]
