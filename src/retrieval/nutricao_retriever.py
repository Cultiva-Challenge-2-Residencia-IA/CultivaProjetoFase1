"""Interface e implementação do Retriever canônico para a aba de Nutrição.

Contrato comum entre a camada de Corpus e o Retriever (CULTIVA - Fase 1 / Aba Nutrição).
Atende a RF-IA06 (foco exclusivo na aba Nutrição nesta fase), RN04, RN16 e RN17.
"""

from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

from src.config import MAX_CHUNKS_PER_DOC, TOP_K_FINAL
from src.models.schemas import Trecho, TrechoRecuperado
from src.retrieval.hybrid_retriever import HybridRetriever


@runtime_checkable
class NutricaoRetrieverProtocol(Protocol):
    """
    Protocolo formal canônico para o Retriever de Nutrição.
    Entrada: consulta (str), k (int).
    Saída: Trechos com scores (List[TrechoRecuperado]).
    Restrito exclusivamente à aba de Nutrição nesta fase.
    """

    def recuperar(self, consulta: str, k: int = 4) -> List[TrechoRecuperado]:
        """
        Recupera os k trechos mais relevantes do corpus de Nutrição para a consulta.

        Args:
            consulta: Texto da dúvida ou consulta nutricional.
            k: Quantidade de trechos a retornar (padrão: 4).

        Returns:
            Lista de TrechoRecuperado contendo o Trecho e seus scores detalhados.
        """
        ...


class NutricaoHybridRetriever:
    """
    Retriever Híbrido especializado para a aba de Nutrição.
    Implementa NutricaoRetrieverProtocol com governança de fontes (RN04, RN16, RN17).
    """

    def __init__(
        self,
        trechos: Optional[List[Trecho]] = None,
        apenas_aprovados: bool = False,
        underlying_retriever: Optional[HybridRetriever] = None,
    ) -> None:
        """
        Inicializa o retriever com uma lista de Trechos ou um retriever subjacente.

        Args:
            trechos: Lista de Trecho indexáveis.
            apenas_aprovados: Se True, filtra trechos cujo approval_status != 'aprovado'.
            underlying_retriever: Instância opcional de HybridRetriever para reaproveitamento.
        """
        self.apenas_aprovados = apenas_aprovados
        self._trechos_map: Dict[str, Trecho] = {}

        if trechos is not None:
            if apenas_aprovados:
                filtered_trechos = [t for t in trechos if t.approval_status == "aprovado"]
            else:
                filtered_trechos = trechos

            for t in filtered_trechos:
                self._trechos_map[t.id] = t

            legacy_chunks = [t.to_document_chunk() for t in filtered_trechos]
            self.internal_retriever = HybridRetriever(legacy_chunks)
        elif underlying_retriever is not None:
            self.internal_retriever = underlying_retriever
            for c in underlying_retriever.chunks:
                t = Trecho.from_document_chunk(c)
                self._trechos_map[t.id] = t
        else:
            self.internal_retriever = HybridRetriever([])

    def recuperar(self, consulta: str, k: int = TOP_K_FINAL) -> List[TrechoRecuperado]:
        """
        Executa a recuperação híbrida retornando Trechos com scores estruturados.
        Entrada: consulta, k.
        Saída: List[TrechoRecuperado].
        """
        if not consulta or not consulta.strip():
            return []

        legacy_results = self.internal_retriever.retrieve(
            query=consulta,
            top_k=k,
            max_chunks_per_doc=MAX_CHUNKS_PER_DOC,
        )

        scored_trechos: List[TrechoRecuperado] = []
        for rank_idx, r in enumerate(legacy_results, start=1):
            trecho = self._trechos_map.get(r.chunk.chunk_id)
            if trecho is None:
                trecho = Trecho.from_document_chunk(r.chunk)

            if self.apenas_aprovados and trecho.approval_status != "aprovado":
                continue

            trecho_recuperado = TrechoRecuperado.from_retrieved_chunk(
                rc=r,
                licenca=trecho.licenca,
                approval_status=trecho.approval_status,
                pagina_pdf=trecho.pagina_pdf,
                rank=rank_idx,
            )
            trecho_recuperado.trecho = trecho
            scored_trechos.append(trecho_recuperado)

        return scored_trechos[:k]

    # Compatibilidade com interface legada
    def retrieve(self, query: str, top_k: int = TOP_K_FINAL) -> List[Any]:
        return self.internal_retriever.retrieve(query, top_k=top_k)
