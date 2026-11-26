"""Demonstração da entrega multimodal (issue #97): o fluxo de falhas roda sem o Ollama."""

import pytest

from src.multimodal import imagem
from src.multimodal.pdf import AVISO_INJECAO

pytestmark = pytest.mark.skipif(not (imagem.TESSDATA / "por.traineddata").exists(),
                                reason="modelo OCR ausente (corpus/.cache/tessdata)")


def test_fluxo_de_falhas_nao_chama_o_modelo_e_registra_as_entradas():
    from src.demo_multimodal import Relato, fluxo_falhas

    relato, artefatos = Relato(), {}
    resultado = fluxo_falhas(relato, artefatos)
    assert resultado["injecao"]["resposta_fixa"] == AVISO_INJECAO
    assert resultado["sem_texto"]["resposta_fixa"] == imagem.SEM_TEXTO
    assert "188" in resultado["risco"]["resposta_fixa"]
    assert set(artefatos) == {"entradas/cardapio_com_instrucao_escondida.pdf", "entradas/imagem_sem_texto.png"}
    assert any("sem chamar o modelo" in linha for linha in relato.linhas)
