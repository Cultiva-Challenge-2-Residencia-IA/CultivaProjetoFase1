"""Ablação do `seed_guidelines` (issue #5).

Mede, com o mesmo código, o mesmo corpus aprovado e as mesmas perguntas, o efeito de devolver ao
índice as 10 "sínteses normativas" de `data/raw/guidelines/seed_guidelines.json`, que não têm
procedência verificável e saíram no PR #30. Só mede: o `seed` não volta ao índice.

Critérios definidos antes da execução: eval/runs/ablacao_seed_issue5_criterios.md.

    uv run python -m src.evaluation.ablacao_seed
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from src.agent.consultant_baseline import NutritionConsultantBaseline
from src.config import BENCHMARK_QUESTIONS_PATH, DATA_DIR
from src.evaluation import benchmark_v2
from src.evaluation.run_benchmark import evaluate_baseline
from src.ingestion.contextual_chunker import ContextualChunker
from src.models.schemas import DocumentChunk
from src.rag.corpus_loader import carregar_chunks_do_corpus

SEED_PATH = DATA_DIR / "raw" / "guidelines" / "seed_guidelines.json"
SAIDA_PADRAO = Path("eval/runs/ablacao_seed_issue5.json")
PREFIXO_SEED = "DOC_"
K = 4

ESTAGIOS = [
    ("E1", "Só RAG", False, False),
    ("E2", "RAG + TACO", True, False),
    ("E3", "RAG + TACO + grafo (configuração da entrega)", True, True),
]
METRICAS_V2 = ("acerto_trecho_at_k", "mrr_trecho", "ndcg_trecho_at_k", "cobertura_termos", "guardrail_acuracia")


def carregar_seed(caminho: Path = SEED_PATH) -> List[DocumentChunk]:
    """Trechos do `seed`, montados como no modo legado (`ContextualChunker`)."""
    return ContextualChunker().load_and_chunk_json(caminho)


def _eh_seed(identificador: str) -> bool:
    return identificador.startswith(PREFIXO_SEED)


def presenca_seed(listas: List[List[str]], k: int = K) -> Dict[str, Any]:
    """Fração das posições do top-k ocupadas pelo `seed` e quantas consultas têm ao menos um."""
    posicoes = [d for lista in listas for d in lista[:k]]
    com_seed = sum(1 for lista in listas if any(_eh_seed(d) for d in lista[:k]))
    return {
        "posicoes_top_k": len(posicoes),
        "posicoes_seed": sum(1 for d in posicoes if _eh_seed(d)),
        "fracao_seed": round(sum(1 for d in posicoes if _eh_seed(d)) / max(len(posicoes), 1), 4),
        "consultas_com_seed": com_seed,
        "consultas": len(listas),
    }


def regua_antiga(perguntas: List[Dict[str, Any]], relatorio: Dict[str, Any], k: int = K) -> Dict[str, Any]:
    """Nas perguntas do v1 que esperam algum `DOC_*`: algum deles aparece no top-k?"""
    recuperados = {q["id"]: q["retrieved_doc_ids"][:k] for q in relatorio["question_results"]}
    por_pergunta = {}
    for p in perguntas:
        esperados = [d for d in p["expected_doc_ids"] if _eh_seed(d)]
        if esperados:
            achados = [d for d in esperados if d in recuperados.get(p["id"], [])]
            por_pergunta[p["id"]] = {"esperados_seed": esperados, "achados_no_top_k": achados}
    return {
        "perguntas_que_esperam_seed": len(por_pergunta),
        "com_seed_esperado_no_top_k": sum(1 for v in por_pergunta.values() if v["achados_no_top_k"]),
        "por_pergunta": por_pergunta,
    }


def avaliar_v2(consultor: NutritionConsultantBaseline, k: int = K) -> Dict[str, Any]:
    """Benchmark v2 no índice do consultor. Trecho do `seed` no top-k conta como irrelevante."""
    casos = benchmark_v2.carregar_casos()
    resultados = [benchmark_v2.avaliar_caso(c, consultor.consult(c["pergunta"], top_k=k), k) for c in casos]
    rel = benchmark_v2.montar_relatorio(casos, resultados, k)
    return {
        "por_split": {s: {m: rel["por_split"][s][m] for m in METRICAS_V2} for s in benchmark_v2.SPLITS},
        "rr_por_caso": {r["id"]: r["rr_trecho"] for r in resultados if "rr_trecho" in r},
        "presenca_seed": presenca_seed([r["trechos_recuperados"] for r in resultados], k),
        "nao_julgados_fora_do_seed": {
            r["id"]: [t for t in r["nao_julgados_no_top_k"] if not _eh_seed(t)]
            for r in resultados
            if any(not _eh_seed(t) for t in r.get("nao_julgados_no_top_k", []))
        },
    }


def _ajustar_estagio(consultor: NutritionConsultantBaseline, taco, grafo, usar_taco: bool, usar_grafo: bool) -> None:
    consultor.enable_taco_tool, consultor.taco_tool = usar_taco, (taco if usar_taco else None)
    consultor.enable_graph_engine, consultor.graph_engine = usar_grafo, (grafo if usar_grafo else None)


def rodar_condicao(chunks: List[DocumentChunk], perguntas: List[Dict[str, Any]]) -> Dict[str, Any]:
    consultor = NutritionConsultantBaseline(chunks=chunks, enable_ollama=False)
    taco, grafo = consultor.taco_tool, consultor.graph_engine
    estagios = {}
    for eid, descricao, usar_taco, usar_grafo in ESTAGIOS:
        _ajustar_estagio(consultor, taco, grafo, usar_taco, usar_grafo)
        rep = evaluate_baseline(enable_ollama=False, consultant=consultor, write_report=False)
        estagios[eid] = {
            "descricao": descricao,
            "geral": rep["overall_metrics"],
            "por_categoria": {
                c: {"recall_at_k": m["mean_doc_recall_at_k"], "mrr": m["mean_mrr"],
                    "cobertura": m["mean_keyword_coverage"]}
                for c, m in rep["metrics_by_category"].items()
            },
            "por_pergunta": {
                q["id"]: {"rr": q["reciprocal_rank"], "recall": q["doc_recall_at_k"],
                          "cobertura": q["keyword_coverage"], "top4": q["retrieved_doc_ids"][:K]}
                for q in rep["question_results"]
            },
            "presenca_seed_v1": presenca_seed([q["retrieved_doc_ids"] for q in rep["question_results"]]),
            "regua_antiga_v1": regua_antiga(perguntas, rep),
        }
    # O v2 roda só na configuração da entrega (E3); TACO e grafo não mudam a busca de Trechos.
    _ajustar_estagio(consultor, taco, grafo, True, True)
    return {"trechos_no_indice": len(chunks), "estagios": estagios, "v2_E3": avaliar_v2(consultor)}


def rodar(saida: Path = SAIDA_PADRAO) -> Dict[str, Any]:
    perguntas = json.loads(BENCHMARK_QUESTIONS_PATH.read_text(encoding="utf-8"))
    corpus = carregar_chunks_do_corpus()
    seed = carregar_seed()
    relatorio = {
        "criterios": "eval/runs/ablacao_seed_issue5_criterios.md",
        "golden_set": {"v1": str(BENCHMARK_QUESTIONS_PATH.relative_to(DATA_DIR.parent)),
                       "v2": "eval/golden/v2/{dev,test}.json"},
        "configuracao": "sem LLM (síntese extrativa), parâmetros padrão de src/config.py, k=4",
        "seed": {"arquivo": "data/raw/guidelines/seed_guidelines.json",
                 "documentos": sorted({c.doc_id for c in seed}), "trechos": len(seed)},
        "condicoes": {
            "S0": {"descricao": "Fontes aprovadas (índice atual)", **rodar_condicao(corpus, perguntas)},
            "S1": {"descricao": "Fontes aprovadas + seed_guidelines", **rodar_condicao(corpus + seed, perguntas)},
        },
    }
    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text(json.dumps(relatorio, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return relatorio


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--saida", type=Path, default=SAIDA_PADRAO)
    args = parser.parse_args()
    rel = rodar(args.saida)
    print(f"{'':4s}{'':4s}{'recall@4':>9s}{'MRR':>8s}{'cobert.':>9s}{'guard.':>8s}{'seed top4':>11s}")
    for cid, cond in rel["condicoes"].items():
        for eid, e in cond["estagios"].items():
            g = e["geral"]
            print(f"{cid:4s}{eid:4s}{g['mean_doc_recall_at_k']:9.4f}{g['mean_reciprocal_rank_mrr']:8.4f}"
                  f"{g['mean_keyword_coverage']:9.4f}{g['legal_guardrail_accuracy']:8.4f}"
                  f"{e['presenca_seed_v1']['fracao_seed']:11.4f}")
    for cid, cond in rel["condicoes"].items():
        for split, m in cond["v2_E3"]["por_split"].items():
            print(f"v2 {cid} {split:5s} " + " ".join(f"{k}={v}" for k, v in m.items()))
    print(f"Relatório: {args.saida}")


if __name__ == "__main__":
    main()
