"""Demonstração da entrega multimodal (issue #97): fluxo de falhas e rótulo simulado rodam sem o Ollama."""

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


def test_fluxo_rotulo_usa_ler_com_visao_publico_e_sinaliza_discordancia(monkeypatch):
    import src.demo_multimodal as demo

    class _RetrieverVazio:
        def retrieve(self, _consulta: str, top_k: int = 3):
            return []

    def visao_simulada(_dados: bytes, _modelo: str, _base_url: str):
        return {
            "tem_tabela": True,
            "porcao": "30 g (1 xícara)",
            "nutrientes": [
                {"campo": "valor_energetico", "por_100": "412", "por_porcao": "124"},
                {"campo": "gorduras_totais", "por_100": "0", "por_porcao": "0"},
            ],
        }

    monkeypatch.setattr(demo, "ler_com_visao", visao_simulada)
    relato, artefatos = demo.Relato(), {}
    saida = demo.fluxo_rotulo(relato, _RetrieverVazio(), com_llm=True, artefatos=artefatos)
    assert "entradas/rotulo_cereal.png" in artefatos
    assert saida["resultado"]["tem_tabela"] is True
    assert "Gorduras totais" in saida["resultado"]["nao_confirmados"]
    assert any("| Valor energético (kcal) | 412 / 124 | 412 / 124 | 412 / 124 |" in linha for linha in relato.linhas)
