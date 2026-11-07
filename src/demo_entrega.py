"""
Script de Demonstração Oficial da Entrega (Artefatos + Recuperação + Fundamentação + Rastreabilidade).

Execução:
    uv run python -m src.demo_entrega
    uv run python -m src.demo_entrega "Sua pergunta nutricional personalizada aqui"
"""

import sys
from collections import Counter
from typing import List

from src.agent.consultant_baseline import NutritionConsultantBaseline


DEMO_QUERIES: List[str] = [
    "Como a fibra solúvel da aveia age para reduzir o colesterol LDL e a glicemia?",
    "Quais são as quatro categorias de alimentos definidas pelo Guia Alimentar e por que os ultraprocessados prejudicam a saciedade?",
    "Tenho 78kg, 1,70m e pré-diabetes. Monte um cardápio completo de 1800 kcal com café da manhã, almoço e jantar para mim.",
]


def print_artifacts_summary(consultant: NutritionConsultantBaseline) -> None:
    chunks = consultant.chunks
    inventory = consultant.chunker.get_curated_sources_inventory(chunks)
    by_type = Counter(item.source_type for item in inventory)
    vstats = (
        consultant.retriever.vector_store.get_stats()
        if consultant.retriever.vector_store is not None
        else {}
    )

    print("=" * 92)
    print("PARTE 1 — AUDITORIA DOS ARTEFATOS DA ENTREGA (BASE CURADA, CHUNKING, EMBEDDINGS E VECTOR DB)")
    print("=" * 92)
    print(f"1. Base de Conhecimento Curada : {len(chunks)} chunks contextualizados prontos para busca")
    print(
        f"2. Total de Documentos-Fonte   : {len(inventory)} documentos-fonte únicos "
        f"(Requisito mínimo: >= 20 documentos-fonte)"
    )
    print(
        f"   • PDFs Oficiais (corpus/manifest.yaml) : {by_type['PDF_OFICIAL_CORPUS']} documentos completos "
        "(MS Guia 2014, Fascículo 2021, SciELO 2013/2014/2020, SVB 2012)"
    )
    print(
        f"   • Artigos Reais PubMed (PMID / DOI)    : {by_type['PUBMED_PEER_REVIEWED']} meta-análises/revisões sistemáticas"
    )
    print(
        f"   • Sínteses de Diretrizes Clínicas      : {by_type['CLINICAL_SYNTHESIS']} diretrizes (SBD, SBC, ISSN, IOC)"
    )
    print(
        "3. Estratégia de Chunking      : Page-Aware & Section-Aware Chunking (prepare_rag.py, 80-1400 chars) + "
        "Contextual Retrieval Header (ContextualChunker, máx. 1200 chars por sentença)"
    )
    print(
        f"4. Estratégia de Embeddings    : {vstats.get('embedding_model')} "
        f"({vstats.get('embedding_dimension')} dimensões, {vstats.get('distance_metric')})"
    )
    print(
        f"5. Banco Vetorial Implementado : {vstats.get('vector_db_engine')}\n"
        f"   • Persistência em Disco     : {vstats.get('persist_directory')}\n"
        f"   • Coleção / Vetores Ativos  : {vstats.get('collection_name')} "
        f"({vstats.get('total_vectors_indexed')} vetores persistidos)"
    )
    print("-" * 92)
    print("AMOSTRA DO CATÁLOGO DE DOCUMENTOS-FONTE VERIFICÁVEIS (PRIMEIROS 22 DE 47):")
    for idx, src in enumerate(inventory[:22], start=1):
        print(
            f"  {idx:02d}. [{src.source_id}] ({src.source_type} | {src.publication_year}) "
            f"{src.title[:62]}... | Licença: {src.license} | Status: {src.review_status}"
        )
    print("=" * 92)


def run_single_demo(consultant: NutritionConsultantBaseline, query: str, idx: int) -> None:
    res = consultant.consult(query, top_k=4)
    print(f"\n{'#' * 92}")
    print(f"DEMONSTRAÇÃO #{idx} — FLUXO COMPLETO DE RECUPERAÇÃO, FUNDAMENTAÇÃO E RASTREABILIDADE")
    print(f"{'#' * 92}")

    # Item 1 da Demonstração: Consulta submetida ao sistema
    print("\n[ETAPA A — CONSULTA SUBMETIDA AO SISTEMA]")
    print(f"  • Pergunta Original : {res.original_query}")
    print(f"  • Guardrail Ativado : {res.guardrail_triggered} (Categoria: {res.intent_category})")
    if res.guardrail_triggered:
        print(f"  • Query Reenquadrada: {res.effective_query}")
        print(f"  • Aviso Legal (CFN) : {res.legal_compliance_notice}")

    # Item 2 da Demonstração: Recuperação dos chunks ou documentos mais relevantes
    print("\n[ETAPA B — RECUPERAÇÃO DOS CHUNKS MAIS RELEVANTES (BANCO VETORIAL CHROMADB + BM25 + RRF)]")
    for rank, rc in enumerate(res.retrieved_chunks, start=1):
        c = rc.chunk
        excerpt = c.raw_text[:260].replace("\n", " ") + ("..." if len(c.raw_text) > 260 else "")
        print(
            f"  Chunk #{rank}: [{c.chunk_id}] (Doc: {c.doc_id} | Fonte: {c.source_id} | Evidência: {c.evidence_level})\n"
            f"    ├─ Seção / Localização : {c.section_path}\n"
            f"    ├─ Scores de Busca     : Rerank={rc.rerank_score:.4f} | RRF={rc.rrf_score:.4f} | "
            f"Vetorial(ChromaDB)={rc.vector_score:.4f} (rank={rc.vector_rank}) | BM25={rc.bm25_score:.4f} (rank={rc.bm25_rank})\n"
            f"    └─ Conteúdo Recuperado : \"{excerpt}\""
        )

    # Item 3 da Demonstração: Resposta fundamentada no conteúdo recuperado
    print("\n[ETAPA C — RESPOSTA FUNDAMENTADA NO CONTEÚDO RECUPERADO]")
    print(f"  • Motor de Síntese : {res.model_used} | Modo: {res.retrieval_mode} | Evidência: {res.evidence_grade}")
    print(f"  • Síntese Direta   :\n    {res.evidence_summary}")
    print(f"  • Mecanismo        :\n    {res.physiological_mechanism}")
    print(f"  • Achados Clínicos :\n    {res.protocol_findings}")

    # Item 4 da Demonstração: Evidência das fontes utilizadas na resposta
    print("\n[ETAPA D — EVIDÊNCIA RASTREÁVEL DAS FONTES UTILIZADAS NA RESPOSTA]")
    for cite_idx, cite in enumerate(res.citations, start=1):
        print(f"  [{cite_idx}] {cite}")
    print("-" * 92)


def main() -> None:
    consultant = NutritionConsultantBaseline(enable_ollama=True)
    print_artifacts_summary(consultant)

    queries = [" ".join(sys.argv[1:])] if len(sys.argv) > 1 else DEMO_QUERIES
    for i, q in enumerate(queries, start=1):
        run_single_demo(consultant, q, i)


if __name__ == "__main__":
    main()
