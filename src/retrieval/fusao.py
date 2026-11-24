"""Fusão de várias listas de Trechos por Reciprocal Rank Fusion (issue #99).

Usada quando a busca roda com mais de uma consulta (pergunta original, subpergunta e trecho
hipotético da reescrita): cada lista contribui 1/(k + posição) para o Trecho, e o Trecho achado por
mais de uma consulta sobe. Com uma lista só, a ordem não muda.
"""

from typing import Dict, List, Sequence

from src.config import MAX_CHUNKS_PER_DOC
from src.models.schemas import RetrievedChunk

K_RRF = 60


def fundir_rrf(listas: Sequence[Sequence[RetrievedChunk]], top_k: int, k: int = K_RRF,
               max_por_documento: int = MAX_CHUNKS_PER_DOC) -> List[RetrievedChunk]:
    """Funde as listas e mantém o limite de Trechos por documento da busca híbrida (0 = sem limite)."""
    pontos: Dict[str, float] = {}
    primeiro: Dict[str, RetrievedChunk] = {}
    for lista in listas:
        for posicao, item in enumerate(lista, start=1):
            cid = item.chunk.chunk_id
            pontos[cid] = pontos.get(cid, 0.0) + 1.0 / (k + posicao)
            primeiro.setdefault(cid, item)
    ordem = sorted(pontos, key=lambda cid: (-pontos[cid], list(primeiro).index(cid)))
    fundidos: List[RetrievedChunk] = []
    por_documento: Dict[str, int] = {}
    for cid in ordem:
        doc = primeiro[cid].chunk.doc_id
        if max_por_documento and por_documento.get(doc, 0) >= max_por_documento:
            continue
        por_documento[doc] = por_documento.get(doc, 0) + 1
        fundidos.append(primeiro[cid].model_copy(update={"rrf_score": round(pontos[cid], 6)}))
        if len(fundidos) == top_k:
            break
    return fundidos
