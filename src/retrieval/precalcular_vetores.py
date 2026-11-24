"""Pré-calcula os vetores dos Trechos no cache de embeddings (issue #15, ADR 0006).

O CI roda este módulo no job de avaliação: na `main`, o cache resultante é salvo e passa a ser
restaurado pelos PRs, que só calculam os Trechos novos ou alterados. Por padrão, cobre o que o CI usa
(fontes aprovadas de Nutrição); `--todas` inclui as pendentes e a Saúde Física, para uso local.

    uv run python -m src.retrieval.precalcular_vetores [--todas]
"""

import argparse
import time

from src.config import (
    CORPUS_RAG_DIR,
    CORPUS_RAG_DIR_SAUDE_FISICA,
    EMBEDDING_CACHE_PATH,
    EMBEDDING_MODEL_NAME,
    EMBEDDING_NORMALIZAR_TEXTO,
)
from src.rag.corpus_loader import carregar_chunks_do_corpus
from src.retrieval.vector_store import CacheDeVetores, DenseMultilingualEmbedder


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--todas", action="store_true",
                        help="Inclui as fontes pendentes e as de Saúde Física, além das aprovadas de Nutrição")
    args = parser.parse_args()
    if EMBEDDING_CACHE_PATH is None:
        parser.error("EMBEDDING_CACHE_PATH está vazio: não há cache para pré-calcular.")
    chunks = carregar_chunks_do_corpus(incluir_pendentes=args.todas, rag_dir=CORPUS_RAG_DIR)
    if args.todas:
        chunks += carregar_chunks_do_corpus(incluir_pendentes=True, rag_dir=CORPUS_RAG_DIR_SAUDE_FISICA)
    embedder = DenseMultilingualEmbedder(model_name=EMBEDDING_MODEL_NAME, normalizar_texto=EMBEDDING_NORMALIZAR_TEXTO)
    inicio = time.monotonic()
    embedder.embed_documents([embedder.preparar_documento(c.contextualized_text) for c in chunks],
                             cache=CacheDeVetores(EMBEDDING_CACHE_PATH))
    print(f"{EMBEDDING_MODEL_NAME}: {len(chunks)} Trechos, {embedder.calculados} calculados agora, "
          f"{len(chunks) - embedder.calculados} vindos do cache, em {time.monotonic() - inicio:.0f} s "
          f"({EMBEDDING_CACHE_PATH}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
