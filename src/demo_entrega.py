"""
Script de Demonstração Oficial da Entrega (Artefatos + Recuperação + Fundamentação + Rastreabilidade).

Execução:
    uv run python -m src.demo_entrega
    uv run python -m src.demo_entrega "Sua pergunta nutricional personalizada aqui"
    uv run python -m src.demo_entrega --salvar-artefatos   # regrava entrega_semanal/
"""

import contextlib
import io
import json
import sys
from collections import Counter
from pathlib import Path
from typing import List

from src.config import PROJECT_ROOT

from src.agent.consultant_baseline import NutritionConsultantBaseline
from src.rag.corpus_loader import inventario_de_fontes


DEMO_QUERIES: List[str] = [
    "Como a fibra solúvel da aveia age para reduzir o colesterol LDL e a glicemia?",
    "Quais são as quatro categorias de alimentos definidas pelo Guia Alimentar e por que os ultraprocessados prejudicam a saciedade?",
    "Tenho 78kg, 1,70m e pré-diabetes. Monte um cardápio completo de 1800 kcal com café da manhã, almoço e jantar para mim.",
]


def print_artifacts_summary(consultant: NutritionConsultantBaseline) -> None:
    chunks = consultant.chunks
    inventory = inventario_de_fontes(chunks)
    by_kind = Counter(item.kind for item in inventory)
    by_type = Counter(item.tipo_fonte for item in inventory)
    by_status = Counter(item.approval_status for item in inventory)
    vstats = (
        consultant.retriever.vector_store.get_stats()
        if consultant.retriever.vector_store is not None
        else {}
    )

    print("=" * 92)
    print("PARTE 1 — AUDITORIA DOS ARTEFATOS DA ENTREGA (BASE CURADA, CHUNKING, EMBEDDINGS E VECTOR DB)")
    print("=" * 92)
    if consultant.incluir_pendentes:
        print(
            "AVISO: modo de desenvolvimento. O índice inclui fontes com approval_status 'pendente' "
            "(flag explícita). Em produção, só fontes 'aprovado' entram (ADR 0002, issue #7)."
        )
    print(f"1. Base de Conhecimento Curada : {len(chunks)} Trechos indexados (corpus/nutricao/rag/*.jsonl)")
    print(
        f"2. Total de Documentos-Fonte   : {len(inventory)} documentos-fonte catalogados em corpus/manifest.yaml "
        f"(requisito mínimo: >= 20)"
    )
    print(f"   • PDFs do corpus (SHA-256, página do PDF)     : {by_kind.get('pdf', 0)}")
    print(f"   • Resumos do PubMed (PMID e DOI)              : {by_kind.get('resumo_pubmed', 0)}")
    print(f"   • Por tipo de fonte                           : {dict(sorted(by_type.items()))}")
    print(f"   • Por status de aprovação                     : {dict(sorted(by_status.items()))}")
    print(
        "3. Estratégia de Chunking      : Trechos de ~1000 caracteres (máx. 1400) sem atravessar página nem seção, "
        "gerados por corpus/scripts/prepare_rag.py, com cabeçalho contextual na indexação (ADR 0002)"
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
    print(f"CATÁLOGO DOS DOCUMENTOS-FONTE INDEXADOS ({len(inventory)}):")
    for idx, src in enumerate(inventory, start=1):
        print(
            f"  {idx:02d}. [{src.fonte_id}] ({src.kind} | {src.tipo_fonte} | {src.publication_year}) "
            f"{src.title[:58]}... | {src.chunks_count} Trechos | Licença: {src.licenca} | Aprovação: {src.approval_status}"
        )
    print("=" * 92)


def run_single_demo(consultant: NutritionConsultantBaseline, query: str, idx: int):
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
            f"  Chunk #{rank}: [{c.chunk_id}] (Fonte: {c.doc_id} | Pág. PDF: {c.pagina_pdf or '-'} | Evidência: {c.evidence_level} | Aprovação: {c.approval_status})\n"
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
    return res


class _Tee(io.TextIOBase):
    """Escreve no terminal e guarda o texto, para o log da demonstração."""

    def __init__(self, destino) -> None:
        self.destino, self.partes = destino, []

    def write(self, texto: str) -> int:
        self.partes.append(texto)
        return self.destino.write(texto)


def salvar_artefatos(consultant: NutritionConsultantBaseline, respostas, log: str, base: Path) -> None:
    """Regrava os artefatos da entrega a partir do sistema real (sem números escritos à mão)."""
    artefatos, demo = base / "artefatos", base / "demonstracao"
    artefatos.mkdir(parents=True, exist_ok=True)
    demo.mkdir(parents=True, exist_ok=True)
    inventario = inventario_de_fontes(consultant.chunks)
    amostra, vistos = [], set()
    for c in consultant.chunks:
        if c.doc_id not in vistos:
            vistos.add(c.doc_id)
            amostra.append(c.model_dump())
    vstats = consultant.retriever.vector_store.get_stats() if consultant.retriever.vector_store else {}
    estatisticas = {
        **vstats,
        "trechos_indexados": len(consultant.chunks),
        "documentos_fonte": len(inventario),
        "fontes_pdf": sum(1 for f in inventario if f.kind == "pdf"),
        "resumos_pubmed": sum(1 for f in inventario if f.kind == "resumo_pubmed"),
        "inclui_fontes_pendentes": consultant.incluir_pendentes,
    }

    def gravar(caminho: Path, dados) -> None:
        caminho.write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    gravar(artefatos / "inventario_fontes_curadas.json", [f.model_dump() for f in inventario])
    gravar(artefatos / "amostra_chunks_contextualizados.json", amostra)
    gravar(artefatos / "estatisticas_banco_vetorial.json", estatisticas)
    gravar(demo / "resultado_consultas.json", [r.model_dump() for r in respostas])
    (demo / "log_demonstracao_consultas.txt").write_text(log, encoding="utf-8")


def main() -> None:
    args = [a for a in sys.argv[1:] if a != "--salvar-artefatos"]
    salvar = "--salvar-artefatos" in sys.argv[1:]
    # Demonstração em modo de desenvolvimento: inclui as fontes ainda pendentes de aprovação.
    consultant = NutritionConsultantBaseline(enable_ollama=True, incluir_pendentes=True)
    tee = _Tee(sys.stdout)
    respostas = []
    with contextlib.redirect_stdout(tee):
        print_artifacts_summary(consultant)
        queries = [" ".join(args)] if args else DEMO_QUERIES
        for i, q in enumerate(queries, start=1):
            respostas.append(run_single_demo(consultant, q, i))
    if salvar:
        salvar_artefatos(consultant, respostas, "".join(tee.partes), PROJECT_ROOT / "entrega_semanal")
        print("Artefatos regravados em entrega_semanal/.")


if __name__ == "__main__":
    main()
