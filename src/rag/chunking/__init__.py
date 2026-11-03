"""Carga dos Trechos do Corpus.

Nesta fase os Trechos vêm prontos de uma fixture (RAG simulado). A divisão real dos
documentos em Trechos entra com a ingestão do Corpus.
"""

from pathlib import Path

import yaml

from dominio.modelos import Trecho

RAIZ = Path(__file__).resolve().parents[3]
FIXTURE_PADRAO = RAIZ / "corpus" / "fixtures" / "guia_alimentar_trechos.yaml"


def carregar_trechos(caminho: Path = FIXTURE_PADRAO) -> tuple[Trecho, ...]:
    dados = yaml.safe_load(caminho.read_text(encoding="utf-8"))
    return tuple(
        Trecho(
            id=t["id"],
            fonte_id=dados["fonte_id"],
            titulo_fonte=dados["titulo_fonte"],
            pagina_pdf=t["pagina_pdf"],
            texto=t["texto"],
        )
        for t in dados["trechos"]
    )
