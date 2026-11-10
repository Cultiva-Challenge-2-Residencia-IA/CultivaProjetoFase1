"""Ablação do ranking da busca híbrida (issue #35).

Mede, sobre o mesmo índice e o mesmo golden set, o efeito de cada componente do
ranking: bônus de evidência, sobreposição de termos, pesos do RRF e a mistura densa
ChromaDB + TF-IDF/LSA. Só mede: não muda a configuração padrão.

Critérios definidos antes da execução: eval/runs/ablacao_mrr_issue35_criterios.md.

    uv run python -m src.evaluation.ablacao_ranking
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Callable, Dict, List

from src.agent.consultant_baseline import NutritionConsultantBaseline
from src.evaluation.run_benchmark import GUIA_CORPUS_ID, evaluate_baseline
from src.retrieval import hybrid_retriever
from src.retrieval.hybrid_retriever import HybridRetriever

SAIDA_PADRAO = Path("eval/runs/ablacao_mrr_issue35.json")
FASCICULO_ID = "protocolos-guia-alimentar-fasciculo1-2021"
PESO_SOBREPOSICAO_ATUAL = 0.25

VARIANTES: List[Dict[str, Any]] = [
    {"id": "A0", "descricao": "Configuração atual", "hipotese": "referência"},
    {"id": "A1", "descricao": "Sem bônus de evidência", "hipotese": "H1", "bonus": False},
    {"id": "A2", "descricao": "Sem sobreposição de termos", "hipotese": "H1", "sobreposicao": 0.0},
    {"id": "A3", "descricao": "RRF puro (sem bônus e sem sobreposição)", "hipotese": "H1",
     "bonus": False, "sobreposicao": 0.0},
    {"id": "A4", "descricao": "RRF com pesos iguais (0,5/0,5)", "hipotese": "pesos do RRF",
     "peso_bm25": 0.5, "peso_denso": 0.5},
    {"id": "A5", "descricao": "Só BM25 (peso denso 0)", "hipotese": "pesos do RRF",
     "peso_bm25": 1.0, "peso_denso": 0.0},
    {"id": "A6", "descricao": "Só busca densa (peso BM25 0)", "hipotese": "pesos do RRF",
     "peso_bm25": 0.0, "peso_denso": 1.0},
    {"id": "A7", "descricao": "Densa só com ChromaDB (sem TF-IDF/LSA)", "hipotese": "H3",
     "modo_denso": "chromadb_pure"},
    {"id": "A8", "descricao": "Densa só com ChromaDB e RRF puro", "hipotese": "H1 + H3",
     "modo_denso": "chromadb_pure", "bonus": False, "sobreposicao": 0.0},
]


def _rerank(peso_sobreposicao: float, bonus: bool) -> Callable:
    """Mesmo cálculo de HybridRetriever._clinical_rerank_score, com componentes ajustáveis."""

    def score(self, query_tokens, chunk, chunk_tokens, rrf_score):
        if not query_tokens:
            return rrf_score
        q_set = set(query_tokens)
        overlap = len(q_set & set(chunk_tokens)) / max(len(q_set), 1)
        grade = hybrid_retriever.EVIDENCE_GRADE_BONUS.get(chunk.evidence_level, 0.0) if bonus else 0.0
        return float(rrf_score + peso_sobreposicao * overlap + grade)

    return score


def mrr_alternativo(report: Dict[str, Any], equivalentes: Dict[str, set]) -> float:
    """MRR aceitando fontes equivalentes (ex.: Fascículo 1 no lugar do Guia). Só informativo."""
    total, n = 0.0, 0
    for q in report["question_results"]:
        if not q["recall_evaluated"]:
            continue
        aceitos = set().union(*map(set, q["expected_sources"]))
        for fonte in list(aceitos):
            aceitos |= equivalentes.get(fonte, set())
        rr = next((1.0 / i for i, d in enumerate(q["retrieved_doc_ids"], 1) if d in aceitos), 0.0)
        total += rr
        n += 1
    return round(total / max(n, 1), 4)


def rodar(saida: Path = SAIDA_PADRAO) -> Dict[str, Any]:
    consultor = NutritionConsultantBaseline(enable_ollama=False)
    retriever: HybridRetriever = consultor.retriever
    original = {
        "peso_bm25": retriever.weight_bm25,
        "peso_denso": retriever.weight_vector,
        "modo_denso": retriever.vector_mode,
    }
    equivalentes = {GUIA_CORPUS_ID: {FASCICULO_ID}}
    resultados = []
    try:
        for v in VARIANTES:
            retriever.weight_bm25 = v.get("peso_bm25", original["peso_bm25"])
            retriever.weight_vector = v.get("peso_denso", original["peso_denso"])
            retriever.vector_mode = v.get("modo_denso", original["modo_denso"])
            HybridRetriever._clinical_rerank_score = _rerank(
                v.get("sobreposicao", PESO_SOBREPOSICAO_ATUAL), v.get("bonus", True)
            )
            rep = evaluate_baseline(enable_ollama=False, consultant=consultor, write_report=False)
            resultados.append({
                **{k: v[k] for k in ("id", "descricao", "hipotese")},
                "parametros": {
                    "peso_bm25": retriever.weight_bm25,
                    "peso_denso": retriever.weight_vector,
                    "modo_denso": retriever.vector_mode,
                    "peso_sobreposicao": v.get("sobreposicao", PESO_SOBREPOSICAO_ATUAL),
                    "bonus_evidencia": v.get("bonus", True),
                },
                "geral": rep["overall_metrics"],
                "mrr_fasciculo_equivalente": mrr_alternativo(rep, equivalentes),
                "por_categoria": {
                    c: {"mrr": m["mean_mrr"], "recall_at_k": m["mean_doc_recall_at_k"]}
                    for c, m in rep["metrics_by_category"].items()
                },
                "rr_por_pergunta": {
                    q["id"]: q["reciprocal_rank"] for q in rep["question_results"] if q["recall_evaluated"]
                },
                "top4_por_pergunta": {
                    q["id"]: q["retrieved_doc_ids"] for q in rep["question_results"] if q["recall_evaluated"]
                },
            })
    finally:
        retriever.weight_bm25 = original["peso_bm25"]
        retriever.weight_vector = original["peso_denso"]
        retriever.vector_mode = original["modo_denso"]
        HybridRetriever._clinical_rerank_score = _ORIGINAL_RERANK

    relatorio = {
        "criterios": "eval/runs/ablacao_mrr_issue35_criterios.md",
        "golden_set": "data/benchmark/eval_questions.json",
        "observacao": "Medido dentro da amostra; o holdout é idêntico ao conjunto de desenvolvimento.",
        "variantes": resultados,
    }
    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text(json.dumps(relatorio, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return relatorio


_ORIGINAL_RERANK = HybridRetriever._clinical_rerank_score


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--saida", type=Path, default=SAIDA_PADRAO)
    args = parser.parse_args()
    rel = rodar(args.saida)
    print(f"{'Id':3} {'Variante':44} {'Recall':>7} {'MRR':>6} {'MRR*':>6} {'Termos':>7} {'Guard':>6}")
    for v in rel["variantes"]:
        g = v["geral"]
        print(f"{v['id']:3} {v['descricao'][:44]:44} {g['mean_doc_recall_at_k']:7.4f} "
              f"{g['mean_reciprocal_rank_mrr']:6.4f} {v['mrr_fasciculo_equivalente']:6.4f} "
              f"{g['mean_keyword_coverage']:7.4f} {g['legal_guardrail_accuracy']:6.4f}")
    print("MRR* = MRR aceitando o Fascículo 1 como equivalente ao Guia (só informativo).")
    print(f"Relatório: {args.saida}")


if __name__ == "__main__":
    main()
