import hashlib
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import chromadb
import numpy as np
from sklearn.preprocessing import normalize

from src.config import (
    PROJECT_ROOT,
    EMBEDDING_CACHE_PATH,
    EMBEDDING_LOTE_MODELO,
    EMBEDDINGS_GPU,
    EMBEDDINGS_GPU_ID,
    EMBEDDING_MODEL_NAME,
    EMBEDDING_NORMALIZAR_TEXTO,
    HNSW_EF_CONSTRUCTION,
    HNSW_EF_SEARCH,
    VECTOR_COLLECTION_NAME,
    VECTOR_STORE_DIR,
)
from src.models.schemas import DocumentChunk
from src.retrieval.hybrid_retriever import expandir_sinonimos

_FASTEMBED_MODEL_CACHE: Dict[str, Any] = {}

# Prefixos (consulta, documento) que o modelo espera. O e5 foi treinado com "query: " e
# "passage: " e perde qualidade sem eles. Modelos ausentes daqui não usam prefixo.
PREFIXOS_EMBEDDING: Dict[str, Tuple[str, str]] = {
    "intfloat/multilingual-e5-large": ("query: ", "passage: "),
}


# Modelo de embeddings dos testes (pytest): hashing de termos, determinístico, sem download e em
# milissegundos. Testa a lógica de indexação, busca, fusão e HNSW, não a qualidade semântica; os
# testes que dependem do modelo real levam a marca `embeddings_reais` (tests/conftest.py).
MODELO_DE_TESTE = "cultiva/hash-teste"
DIMENSAO_DE_TESTE = 512


class EmbeddingsDeTeste:
    """Hashing de palavras e de pares de palavras vizinhas num vetor de `DIMENSAO_DE_TESTE`."""

    def embed(self, textos: List[str], batch_size: Optional[int] = None):
        from src.retrieval.hybrid_retriever import normalize_text

        for texto in textos:
            vetor = np.zeros(DIMENSAO_DE_TESTE, dtype=np.float32)
            palavras = normalize_text(texto).split()
            for termo in palavras + [f"{a} {b}" for a, b in zip(palavras, palavras[1:])]:
                h = int.from_bytes(hashlib.blake2b(termo.encode(), digest_size=8).digest(), "little")
                vetor[h % DIMENSAO_DE_TESTE] += 1.0 if (h >> 32) & 1 else -1.0
            if not vetor.any():
                vetor[0] = 1.0
            yield vetor


def prefixos_do_modelo(modelo: str) -> Tuple[str, str]:
    return PREFIXOS_EMBEDDING.get(modelo, ("", ""))


def dimensao_do_modelo(modelo: str) -> int:
    """Dimensão dos vetores do modelo, segundo o catálogo do fastembed."""
    if modelo == MODELO_DE_TESTE:
        return DIMENSAO_DE_TESTE
    from fastembed import TextEmbedding

    for descricao in TextEmbedding.list_supported_models():
        if descricao["model"] == modelo:
            return int(descricao["dim"])
    raise ValueError(f"modelo de embeddings fora do catálogo do fastembed: {modelo}")


def _caminho_relativo(caminho: Path) -> str:
    """Caminho relativo à raiz do projeto, para não gravar o caminho da máquina em artefatos."""
    try:
        return str(Path(caminho).resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(caminho)


def configuracao_hnsw() -> Dict[str, Any]:
    """Configuração do índice HNSW (cosseno) usada ao criar a coleção."""
    return {
        "space": "cosine",
        "ef_construction": HNSW_EF_CONSTRUCTION,
        "ef_search": HNSW_EF_SEARCH,
    }


def impressao_digital(chunks: List[DocumentChunk], modelo: str,
                      normalizar_texto: bool = EMBEDDING_NORMALIZAR_TEXTO) -> str:
    """Hash do modelo, dos prefixos, do pré-processamento, da configuração do HNSW e do conteúdo.

    Muda quando o corpus, o modelo, a forma de preparar o texto ou o índice mudam, para não
    reaproveitar uma coleção construída com outros parâmetros.
    """
    h = hashlib.sha256(modelo.encode())
    # Só entram quando diferem do comportamento anterior (sem prefixo, texto normalizado), para
    # a coleção do modelo atual continuar com o mesmo nome.
    if any(prefixos_do_modelo(modelo)):
        h.update(repr(prefixos_do_modelo(modelo)).encode())
    if not normalizar_texto:
        h.update(b"texto-original")
    h.update(repr(sorted(configuracao_hnsw().items())).encode())
    for c in chunks:
        h.update(c.chunk_id.encode())
        h.update(c.contextualized_text.encode())
    return h.hexdigest()


def _get_fastembed_model(model_name: str) -> Any:
    """Carrega e mantém em cache de processo o modelo ONNX de embeddings densos."""
    if model_name == MODELO_DE_TESTE:
        return EmbeddingsDeTeste()
    if model_name not in _FASTEMBED_MODEL_CACHE:
        from fastembed import TextEmbedding

        opcoes = {}
        if EMBEDDINGS_GPU:
            import onnxruntime

            # Carrega as bibliotecas CUDA e cuDNN instaladas pelo pip (pacotes nvidia-*).
            if hasattr(onnxruntime, "preload_dlls"):
                onnxruntime.preload_dlls()
            opcoes["providers"] = [("CUDAExecutionProvider", {"device_id": EMBEDDINGS_GPU_ID}), "CPUExecutionProvider"]
        _FASTEMBED_MODEL_CACHE[model_name] = TextEmbedding(model_name=model_name, **opcoes)
    return _FASTEMBED_MODEL_CACHE[model_name]


class CacheDeVetores:
    """Vetores já calculados, por modelo e texto preparado, num SQLite local (issue #15).

    Modelos grandes (o e5-large leva cerca de 19 minutos para o corpus em CPU) tornam caro refazer
    a coleção a cada mudança de Trecho, a cada corpus (aprovadas, pendentes) e a cada teste. A chave
    é o hash do modelo, da versão do fastembed e do texto exatamente como vai ao modelo (prefixo e
    pré-processamento incluídos): só Trechos novos ou alterados são calculados. Guarda só vetores de
    Trechos do corpus, nunca perguntas.
    """

    def __init__(self, caminho: Path) -> None:
        caminho.parent.mkdir(parents=True, exist_ok=True)
        self.caminho = caminho
        self._conexao = sqlite3.connect(str(caminho))
        self._conexao.execute("CREATE TABLE IF NOT EXISTS vetores (chave TEXT PRIMARY KEY, vetor BLOB NOT NULL)")
        self._conexao.commit()

    @staticmethod
    def chave(modelo: str, texto: str) -> str:
        import fastembed

        h = hashlib.sha256(f"{modelo}\0{fastembed.__version__}\0".encode())
        h.update(texto.encode())
        return h.hexdigest()

    def buscar(self, chaves: List[str]) -> Dict[str, np.ndarray]:
        encontrados: Dict[str, np.ndarray] = {}
        for inicio in range(0, len(chaves), 500):
            lote = chaves[inicio:inicio + 500]
            marcas = ",".join("?" * len(lote))
            for chave, blob in self._conexao.execute(
                f"SELECT chave, vetor FROM vetores WHERE chave IN ({marcas})", lote
            ):
                encontrados[chave] = np.frombuffer(blob, dtype=np.float32)
        return encontrados

    def gravar(self, itens: Dict[str, np.ndarray]) -> None:
        self._conexao.executemany(
            "INSERT OR REPLACE INTO vetores (chave, vetor) VALUES (?, ?)",
            [(k, np.asarray(v, dtype=np.float32).tobytes()) for k, v in itens.items()],
        )
        self._conexao.commit()


class DenseMultilingualEmbedder:
    """
    Embeddings densos multilíngues, normalizados em norma L2, gerados localmente pelo fastembed
    (ONNX, CPU): nenhum texto sai da máquina (RNF05; ADR 0006). O modelo vem de
    `EMBEDDING_MODEL_NAME`, e a dimensão e os prefixos de consulta e documento, do próprio modelo.
    """

    def __init__(
        self,
        model_name: str = EMBEDDING_MODEL_NAME,
        normalizar_texto: bool = EMBEDDING_NORMALIZAR_TEXTO,
    ) -> None:
        self.model_name = model_name
        self.dimension = dimensao_do_modelo(model_name)
        self.normalizar_texto = normalizar_texto
        self.prefixo_consulta, self.prefixo_documento = prefixos_do_modelo(model_name)
        self._model = _get_fastembed_model(model_name)
        # Quantos textos a última chamada de `embed_documents` calculou (os demais vieram do cache).
        self.calculados = 0

    def _vetores(self, textos: List[str]) -> np.ndarray:
        brutos = np.array(list(self._model.embed(textos, batch_size=EMBEDDING_LOTE_MODELO)), dtype=np.float32)
        return normalize(brutos, norm="l2")

    def preparar_documento(self, texto: str) -> str:
        return self.prefixo_documento + expandir_sinonimos(texto, self.normalizar_texto)

    def preparar_consulta(self, consulta: str) -> str:
        return self.prefixo_consulta + expandir_sinonimos(consulta, self.normalizar_texto)

    # Lote de cálculo: cada lote é gravado no cache assim que termina, para que uma execução
    # interrompida (job cancelado, tempo limite) não perca os vetores já calculados.
    LOTE_DO_CACHE = 256

    def embed_documents(self, texts: List[str], cache: Optional[CacheDeVetores] = None) -> List[List[float]]:
        """Vetores de textos já preparados (`preparar_documento`). Com `cache`, só calcula os ausentes."""
        if not texts:
            return []
        if cache is None:
            self.calculados = len(texts)
            return self._vetores(texts).tolist()
        chaves = [CacheDeVetores.chave(self.model_name, t) for t in texts]
        encontrados = cache.buscar(list(dict.fromkeys(chaves)))
        faltam = list(dict.fromkeys(t for t, k in zip(texts, chaves) if k not in encontrados))
        self.calculados = len(faltam)
        for inicio in range(0, len(faltam), self.LOTE_DO_CACHE):
            lote = faltam[inicio:inicio + self.LOTE_DO_CACHE]
            novos = {CacheDeVetores.chave(self.model_name, t): v for t, v in zip(lote, self._vetores(lote))}
            cache.gravar(novos)
            encontrados.update(novos)
        return [encontrados[k].tolist() for k in chaves]

    def embed_query(self, query: str) -> List[float]:
        return self._vetores([self.preparar_consulta(query)])[0].tolist()


class NutritionVectorStore:
    """
    Banco de Dados Vetorial Persistente (ChromaDB + Índice HNSW Cosseno):
    Armazena em disco (`data/vector_store/chroma_db`) os embeddings densos do modelo configurado,
    os textos contextualizados dos chunks e os metadados auditáveis de cada fonte científica.
    """

    def __init__(
        self,
        chunks: List[DocumentChunk],
        persist_directory: Optional[Path] = VECTOR_STORE_DIR,
        collection_name: str = VECTOR_COLLECTION_NAME,
        embedding_model_name: str = EMBEDDING_MODEL_NAME,
        use_persistent: bool = True,
        normalizar_texto: bool = EMBEDDING_NORMALIZAR_TEXTO,
        cache_vetores: Optional[Path] = EMBEDDING_CACHE_PATH,
    ) -> None:
        self.chunks = chunks
        self.chunk_id_to_index: Dict[str, int] = {
            c.chunk_id: idx for idx, c in enumerate(chunks)
        }
        self.persist_directory = persist_directory
        # A coleção leva a impressão digital do conteúdo: um corpus ou modelo diferente gera
        # outra coleção, em vez de reaproveitar vetores de uma versão anterior.
        self.fingerprint = impressao_digital(chunks, embedding_model_name, normalizar_texto)
        self.collection_name = f"{collection_name}_{self.fingerprint[:12]}"
        self.embedding_model_name = embedding_model_name
        self.use_persistent = use_persistent and (persist_directory is not None)

        self.embedder = DenseMultilingualEmbedder(
            model_name=embedding_model_name, normalizar_texto=normalizar_texto
        )
        self.cache_vetores = CacheDeVetores(cache_vetores) if cache_vetores is not None else None

        if self.use_persistent and self.persist_directory is not None:
            self.persist_directory.mkdir(parents=True, exist_ok=True)
            self.client = chromadb.PersistentClient(path=str(self.persist_directory))
        else:
            self.client = chromadb.EphemeralClient()

        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            configuration={"hnsw": configuracao_hnsw()},
            metadata={
                "embedding_model": self.embedding_model_name,
                "dimension": str(self.embedder.dimension),
            },
        )
        self._ensure_indexed()

    def _ensure_indexed(self) -> int:
        """
        Verifica se todos os chunks já estão persistidos no ChromaDB.
        Caso o banco em disco já contenha todos os IDs esperados, reutiliza o índice
        persistido imediatamente sem recalcular embeddings.
        """
        if not self.chunks:
            return 0

        expected_ids = [c.chunk_id for c in self.chunks]
        existing_count = self.collection.count()

        if existing_count == len(expected_ids):
            existing = self.collection.get(ids=expected_ids[:5], include=[])
            if len(existing.get("ids", [])) == min(5, len(expected_ids)):
                return existing_count

        return self.index_chunks(self.chunks)

    def index_chunks(self, chunks: List[DocumentChunk], batch_size: int = 128) -> int:
        """Gera os embeddings densos L2-normalizados e persiste no banco vetorial ChromaDB."""
        texts = [self.embedder.preparar_documento(c.contextualized_text) for c in chunks]
        vectors = self.embedder.embed_documents(texts, cache=self.cache_vetores)

        for start in range(0, len(chunks), batch_size):
            end = min(start + batch_size, len(chunks))
            batch_chunks = chunks[start:end]
            batch_vecs = vectors[start:end]

            ids = [c.chunk_id for c in batch_chunks]
            docs = [c.contextualized_text for c in batch_chunks]
            metadatas: List[Dict[str, Any]] = [
                {
                    "chunk_id": c.chunk_id,
                    "doc_id": c.doc_id,
                    "fonte_id": c.doc_id,
                    "title": c.title,
                    "source_organization": c.source_organization,
                    "publication_year": int(c.publication_year),
                    "clinical_domain": c.clinical_domain,
                    "evidence_level": c.evidence_level,
                    "section_path": c.section_path,
                    "fonte_url": c.fonte_url or "",
                    "doi": c.doi or "",
                    "licenca": c.licenca or "pendente",
                    "approval_status": c.approval_status or "pendente",
                    "pagina_pdf": int(c.pagina_pdf) if c.pagina_pdf is not None else -1,
                }
                for c in batch_chunks
            ]

            self.collection.upsert(
                ids=ids,
                embeddings=batch_vecs,
                documents=docs,
                metadatas=metadatas,
            )

        return self.collection.count()

    def similarity_search(
        self,
        query: str,
        top_k: int = 8,
        where: Optional[Dict[str, Any]] = None,
    ) -> List[Tuple[int, float]]:
        """
        Busca por similaridade de cosseno no índice HNSW do ChromaDB.
        Retorna lista de tuplas (chunk_index, cosine_similarity_score).
        A qualidade da busca aproximada depende de `ef_search` (ver `configuracao_hnsw`).
        """
        if not self.chunks:
            return []

        n_results = min(top_k, len(self.chunks))
        query_vec = self.embedder.embed_query(query)

        query_kwargs: Dict[str, Any] = {
            "query_embeddings": [query_vec],
            "n_results": n_results,
            "include": ["distances", "metadatas"],
        }
        if where:
            query_kwargs["where"] = where

        res = self.collection.query(**query_kwargs)
        ids_list = res.get("ids", [[]])[0]
        distances_list = res.get("distances", [[]])[0]

        results: List[Tuple[int, float]] = []
        for chunk_id, dist in zip(ids_list, distances_list):
            if chunk_id in self.chunk_id_to_index:
                idx = self.chunk_id_to_index[chunk_id]
                # No ChromaDB com hnsw:space="cosine", distance = 1.0 - cosine_similarity
                cosine_sim = max(0.0, 1.0 - float(dist))
                results.append((idx, cosine_sim))

        return results

    def get_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas auditáveis do Banco Vetorial persistido."""
        unique_sources = {c.doc_id for c in self.chunks}
        unique_docs = {c.doc_id for c in self.chunks}
        return {
            "vector_db_engine": "ChromaDB (HNSW Cosine Index + SQLite Metadata Store)",
            "persistent": self.use_persistent,
            "persist_directory": _caminho_relativo(self.persist_directory) if self.persist_directory else "in-memory",
            "collection_name": self.collection_name,
            "content_fingerprint": self.fingerprint,
            "embedding_model": self.embedding_model_name,
            "embedding_dimension": self.embedder.dimension,
            "distance_metric": "cosine (L2-normalized vectors)",
            "hnsw": configuracao_hnsw(),
            "total_vectors_indexed": self.collection.count(),
            "unique_doc_ids": len(unique_docs),
            "unique_source_documents": len(unique_sources),
        }
