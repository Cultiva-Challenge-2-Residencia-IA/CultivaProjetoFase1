"""Contrato entre o corpus e o retriever (ADR 0002).

O corpus entrega Trechos em `corpus/nutricao/rag/*.jsonl`, descritos por
`corpus/schemas/trecho.schema.json`. Este módulo converte um Trecho em `DocumentChunk`,
que é o que o retriever indexa, e declara a interface que o retriever precisa cumprir.
"""

from typing import Any, List, Mapping, Protocol, runtime_checkable

from src.config import MAX_CHUNKS_PER_DOC, TOP_K_FINAL
from src.ingestion.contextual_chunker import ContextualChunker
from src.models.schemas import DocumentChunk, RetrievedChunk

# Nível de evidência derivado do tipo da fonte (heurística do ADR 0002, a calibrar com o golden set).
NIVEL_DE_EVIDENCIA = {
    "diretriz": "GUIDELINE_CONSENSUS",
    "norma": "GUIDELINE_CONSENSUS",
    "revisao": "GRADE_B",
    "estudo": "GRADE_C",
}

DOMINIO_CLINICO = "nutricao"


@runtime_checkable
class Retriever(Protocol):
    """Interface do retriever: consulta em, Trechos ordenados por relevância fora.

    Sem efeitos colaterais e determinístico para o mesmo índice. Devolve no máximo `top_k`
    itens, com no máximo `max_chunks_per_doc` por documento. O gate de aprovação é aplicado
    quando o índice é construído, não a cada consulta.
    """

    def retrieve(
        self,
        query: str,
        top_k: int = TOP_K_FINAL,
        max_chunks_per_doc: int = MAX_CHUNKS_PER_DOC,
    ) -> List[RetrievedChunk]: ...


def trecho_para_chunk(trecho: Mapping[str, Any]) -> DocumentChunk:
    """Converte um Trecho do corpus em DocumentChunk, preservando página, link e status."""
    secao = trecho["secao"].strip()
    section_path = f"{secao} (pág. {trecho['pagina_pdf']})" if secao else f"pág. {trecho['pagina_pdf']}"
    organizacao = "; ".join(trecho["instituicoes"])
    nivel = NIVEL_DE_EVIDENCIA[trecho["tipo_fonte"]]
    cabecalho = ContextualChunker.build_context_header(
        title=trecho["titulo_fonte"],
        source_organization=organizacao,
        publication_year=trecho["ano"],
        clinical_domain=DOMINIO_CLINICO,
        evidence_level=nivel,
        section_path=section_path,
    )
    return DocumentChunk(
        chunk_id=trecho["id"],
        doc_id=trecho["fonte_id"],
        title=trecho["titulo_fonte"],
        source_organization=organizacao,
        publication_year=trecho["ano"],
        clinical_domain=DOMINIO_CLINICO,
        evidence_level=nivel,
        section_path=section_path,
        raw_text=trecho["texto"],
        contextualized_text=f"{cabecalho}\n{trecho['texto']}",
        pagina_pdf=trecho["pagina_pdf"],
        fonte_url=trecho["fonte_url"],
        doi=trecho["doi"],
        licenca=trecho["licenca"],
        approval_status=trecho["approval_status"],
    )
