"""Comparação de modelos de embeddings locais (issue #15).

Para cada candidato, troca o banco vetorial do mesmo consultor (BM25, ranking e corpus iguais),
recalibra o limiar do "não sei" no `dev` e mede o benchmark v1 (régua do gate), o v2 (dev para
escolher, test para conferir) e o conjunto do "não sei". Só mede: não muda a configuração padrão.

Critérios definidos antes da execução: eval/runs/comparacao_embeddings_issue15_criterios.md.

    uv run python -m src.evaluation.comparacao_embeddings                 # E0, E1 e E2
    uv run python -m src.evaluation.comparacao_embeddings --modelos E0 E2
    uv run python -m src.evaluation.comparacao_embeddings --modelos E2 --texto-original
"""

from __future__ import annotations

import argparse
import json
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from src.agent.consultant_baseline import NutritionConsultantBaseline
from src.agents.nutricao import grafo as grafo_nutricao
from src.config import ABSTENCAO_CASOS_PATH, BENCHMARK_QUESTIONS_PATH
from src.evaluation import benchmark_v2
from src.evaluation.ablacao_ranking import avaliar_v2
from src.evaluation.run_benchmark import evaluate_baseline
from src.rag.abstencao import fora_do_dominio
from src.retrieval.vector_store import NutritionVectorStore

SAIDA_PADRAO = Path("eval/runs/comparacao_embeddings_issue15.json")

CANDIDATOS: Dict[str, Dict[str, str]] = {
    "E0": {"modelo": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2", "descricao": "MiniLM-L12 multilíngue (atual)"},
    "E1": {"modelo": "sentence-transformers/paraphrase-multilingual-mpnet-base-v2", "descricao": "mpnet-base multilíngue"},
    "E2": {"modelo": "intfloat/multilingual-e5-large", "descricao": "e5-large multilíngue, com prefixos"},
}

# Limiar que nunca dispara o "não sei": usado para medir o cosseno de todas as perguntas.
SEM_ABSTENCAO = -1.0


@contextmanager
def limiar_do_nao_sei(limiar: float) -> Iterator[None]:
    """Troca o limiar lido pelo nó de abstenção do grafo de Nutrição durante a medição."""
    original = grafo_nutricao.ABSTENCAO_LIMIAR_COSSENO
    grafo_nutricao.ABSTENCAO_LIMIAR_COSSENO = limiar
    try:
        yield
    finally:
        grafo_nutricao.ABSTENCAO_LIMIAR_COSSENO = original


def perguntas_de_calibracao() -> List[Dict[str, Any]]:
    """Perguntas do "não sei" (todas) e, como perguntas a responder do `dev`, as do v1 e as do v2
    `dev` com comportamento `responder`."""
    casos = json.loads(ABSTENCAO_CASOS_PATH.read_text(encoding="utf-8"))["casos"]
    perguntas = [
        {"id": c["id"], "pergunta": c["pergunta"], "split": c["split"], "tipo": c["tipo"],
         "esperado": c["esperado"], "origem": "abstencao"}
        for c in casos
    ]
    for q in json.loads(BENCHMARK_QUESTIONS_PATH.read_text(encoding="utf-8")):
        perguntas.append({"id": q["id"], "pergunta": q["query"], "split": "dev", "tipo": "golden_v1",
                          "esperado": "responder", "origem": "v1"})
    for c in benchmark_v2.carregar_casos():
        if c["comportamento_esperado"] == "responder":
            perguntas.append({"id": c["id"], "pergunta": c["pergunta"], "split": c["split"],
                              "tipo": "golden_v2", "esperado": "responder", "origem": "v2"})
    return perguntas


def medir_similaridades(consultor: NutritionConsultantBaseline, perguntas: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Cosseno máximo de cada pergunta, pelo mesmo caminho do grafo (sem disparar o "não sei")."""
    medidas = []
    with limiar_do_nao_sei(SEM_ABSTENCAO):
        for p in perguntas:
            resposta = consultor.consult(p["pergunta"])
            # Sem similaridade: a pergunta parou num portão anterior (risco, injeção) e nunca chega ao "não sei".
            medidas.append({**p, "similaridade": resposta.similaridade_maxima})
    return medidas


def _abstem(m: Dict[str, Any], limiar: float) -> bool:
    return m["similaridade"] is not None and fora_do_dominio(m["pergunta"], m["similaridade"], limiar)


def calibrar_limiar(medidas: List[Dict[str, Any]], passo: float = 0.005) -> Dict[str, Any]:
    """Maior "não sei" fora de Nutrição no `dev` com zero recusas indevidas no `dev`; entre empatados,
    o menor limiar (mais longe das perguntas boas)."""
    dev = [m for m in medidas if m["split"] == "dev"]
    responder = [m for m in dev if m["esperado"] == "responder"]
    fora = [m for m in dev if m["tipo"] == "fora_de_nutricao"]
    melhor: Optional[Dict[str, Any]] = None
    # Limiares inteiros em milésimos: somar o passo em float desalinha o valor gravado do testado.
    for i in range(round(1.0 / passo) + 1):
        limiar = round(i * passo, 4)
        recusas = sum(_abstem(m, limiar) for m in responder)
        if recusas == 0:
            acertos = sum(_abstem(m, limiar) for m in fora)
            if melhor is None or acertos > melhor["fora_de_nutricao_dev"]:
                melhor = {"limiar": limiar, "fora_de_nutricao_dev": acertos}
    assert melhor is not None  # limiar 0 nunca recusa
    melhor["n_fora_de_nutricao_dev"] = len(fora)
    melhor["n_responder_dev"] = len(responder)
    # Folga: menor cosseno entre as perguntas a responder do dev que não têm termo de Nutrição.
    sem_termo = [m["similaridade"] for m in responder
                 if m["similaridade"] is not None and fora_do_dominio(m["pergunta"], m["similaridade"], 2.0)]
    melhor["menor_cosseno_responder_sem_termo_dev"] = round(min(sem_termo), 4) if sem_termo else None
    return melhor


def resumo_abstencao(medidas: List[Dict[str, Any]], limiar: float) -> Dict[str, Any]:
    """Taxas pelo sinal do "não sei" (cosseno e termo). Não conta o desvio do grafo e da TACO, que
    responde quando um deles tem resultado: o `abstention_metrics` do benchmark pode ter menos
    "não sei" em Nutrição fora do corpus, mas nunca mais recusas."""
    def taxa(grupo: List[Dict[str, Any]], abstem: bool) -> Optional[float]:
        return round(sum(_abstem(m, limiar) == abstem for m in grupo) / len(grupo), 4) if grupo else None

    def metricas(filtro) -> Dict[str, Any]:
        sel = [m for m in medidas if filtro(m)]
        return {
            "nao_sei_fora_de_nutricao": taxa([m for m in sel if m["tipo"] == "fora_de_nutricao"], True),
            "nao_sei_nutricao_fora_do_corpus": taxa([m for m in sel if m["tipo"] == "nutricao_fora_do_corpus"], True),
            "respostas_esperadas_conjunto": taxa(
                [m for m in sel if m["origem"] == "abstencao" and m["esperado"] == "responder"], False),
            "respostas_esperadas_golden": taxa([m for m in sel if m["origem"] != "abstencao"], False),
        }

    return {
        "limiar": limiar,
        "geral": metricas(lambda m: True),
        "dev": metricas(lambda m: m["split"] == "dev"),
        "test": metricas(lambda m: m["split"] == "test"),
        "recusas_indevidas": [m["id"] for m in medidas if m["esperado"] == "responder" and _abstem(m, limiar)],
        "fora_de_nutricao_respondidos": [m["id"] for m in medidas if m["tipo"] == "fora_de_nutricao" and not _abstem(m, limiar)],
    }


def latencia_da_busca_densa(consultor: NutritionConsultantBaseline, perguntas: List[str]) -> Dict[str, float]:
    tempos = []
    for p in perguntas:
        inicio = time.perf_counter()
        consultor.retriever.vector_store.similarity_search(p, top_k=consultor.retriever.top_k_vector)
        tempos.append(time.perf_counter() - inicio)
    tempos.sort()
    return {"mediana_ms": round(1000 * tempos[len(tempos) // 2], 1),
            "p95_ms": round(1000 * tempos[int(0.95 * (len(tempos) - 1))], 1)}


def avaliar_candidato(consultor: NutritionConsultantBaseline, cid: str, normalizar_texto: bool,
                      perguntas: List[Dict[str, Any]]) -> Dict[str, Any]:
    modelo = CANDIDATOS[cid]["modelo"]
    inicio = time.perf_counter()
    # Coleção em memória e sem o cache de vetores: cada execução indexa do zero, e o tempo de
    # indexação é comparável entre candidatos.
    consultor.retriever.vector_store = NutritionVectorStore(
        chunks=consultor.chunks, embedding_model_name=modelo, use_persistent=False,
        normalizar_texto=normalizar_texto, cache_vetores=None,
    )
    tempo_indexacao = time.perf_counter() - inicio
    stats = consultor.retriever.vector_store.get_stats()

    medidas = medir_similaridades(consultor, perguntas)
    calibracao = calibrar_limiar(medidas)
    with limiar_do_nao_sei(calibracao["limiar"]):
        v1 = evaluate_baseline(enable_ollama=False, consultant=consultor, write_report=False)
        v2 = avaliar_v2(consultor)

    return {
        "id": cid + ("-texto-original" if not normalizar_texto else ""),
        "modelo": modelo,
        "descricao": CANDIDATOS[cid]["descricao"],
        "normalizar_texto": normalizar_texto,
        "dimensao": stats["embedding_dimension"],
        "vetores": stats["total_vectors_indexed"],
        "tempo_indexacao_s": round(tempo_indexacao, 1),
        "latencia_busca_densa": latencia_da_busca_densa(consultor, [p["pergunta"] for p in perguntas]),
        "calibracao_nao_sei": calibracao,
        "nao_sei": resumo_abstencao(medidas, calibracao["limiar"]),
        "similaridades": {m["id"]: m["similaridade"] for m in medidas},
        "v1": {
            "geral": v1["overall_metrics"],
            "rr_por_pergunta": {q["id"]: q["reciprocal_rank"] for q in v1["question_results"] if q["recall_evaluated"]},
            "top4_por_pergunta": {q["id"]: q["retrieved_doc_ids"] for q in v1["question_results"] if q["recall_evaluated"]},
        },
        "v2": v2,
    }


def rodar(ids: List[str], normalizar_texto: bool = True, saida: Path = SAIDA_PADRAO) -> Dict[str, Any]:
    consultor = NutritionConsultantBaseline(enable_ollama=False)
    if consultor.retriever.vector_mode != "chromadb_pure":
        raise SystemExit("a comparação usa o ranking padrão da #35 (MODO_DENSO=chromadb_pure)")
    perguntas = perguntas_de_calibracao()
    anteriores: Dict[str, Any] = {}
    if saida.exists():
        anteriores = {c["id"]: c for c in json.loads(saida.read_text(encoding="utf-8"))["candidatos"]}
    for cid in ids:
        resultado = avaliar_candidato(consultor, cid, normalizar_texto, perguntas)
        anteriores[resultado["id"]] = resultado
        print(f"{resultado['id']}: indexado em {resultado['tempo_indexacao_s']} s; limiar {resultado['calibracao_nao_sei']['limiar']}")
    relatorio = {
        "criterios": "eval/runs/comparacao_embeddings_issue15_criterios.md",
        "condicoes": {"ranking": "RRF puro sobre BM25 + ChromaDB (A8 da #35)", "top_k": 4,
                      "max_trechos_por_documento": 2, "sintese": "extrativa, sem LLM",
                      "fontes": "aprovadas", "vetores_por_candidato": len(consultor.chunks)},
        "candidatos": [anteriores[k] for k in sorted(anteriores)],
    }
    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text(json.dumps(relatorio, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return relatorio


def imprimir(relatorio: Dict[str, Any]) -> None:
    casos_v2 = {c["id"]: c["split"] for c in benchmark_v2.carregar_casos()}
    print(f"\n{'Id':20} {'Dim':>5} {'Index s':>8} {'Busca ms':>8} {'Limiar':>7} {'v1 MRR':>7} {'v1 Rec':>7} {'v1 Term':>7}")
    for c in relatorio["candidatos"]:
        g = c["v1"]["geral"]
        print(f"{c['id']:20} {c['dimensao']:5d} {c['tempo_indexacao_s']:8.1f} {c['latencia_busca_densa']['mediana_ms']:8.1f} "
              f"{c['calibracao_nao_sei']['limiar']:7.3f} {g['mean_reciprocal_rank_mrr']:7.4f} "
              f"{g['mean_doc_recall_at_k']:7.4f} {g['mean_keyword_coverage']:7.4f}")
    print(f"\n{'Id':20} {'v2':4} {'Trecho':>7} {'Compl.':>7} {'MRR':>6} {'nDCG':>6} {'Termos':>7} {'Guard':>6} {'NãoJulg':>8}")
    for c in relatorio["candidatos"]:
        for split, m in c["v2"]["por_split"].items():
            nj = sum(len(t) for cid, t in c["v2"]["nao_julgados"].items() if casos_v2.get(cid) == split)
            print(f"{c['id']:20} {split:4} {m['acerto_trecho_at_k']:7.4f} {m['acerto_completo_at_k']:7.4f} "
                  f"{m['mrr_trecho']:6.4f} {m['ndcg_trecho_at_k']:6.4f} {m['cobertura_termos']:7.4f} "
                  f"{m['guardrail_acuracia']:6.4f} {nj:8d}")
    print(f"\n{'Id':20} {'Split':5} {'ForaNutr':>8} {'NutrForaCorpus':>14} {'RespConj':>8} {'RespGolden':>10}")
    for c in relatorio["candidatos"]:
        for split in ("dev", "test", "geral"):
            m = c["nao_sei"][split]
            print(f"{c['id']:20} {split:5} {m['nao_sei_fora_de_nutricao']!s:>8} {m['nao_sei_nutricao_fora_do_corpus']!s:>14} "
                  f"{m['respostas_esperadas_conjunto']!s:>8} {m['respostas_esperadas_golden']!s:>10}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--modelos", nargs="+", default=list(CANDIDATOS), choices=list(CANDIDATOS))
    parser.add_argument("--texto-original", action="store_true",
                        help="variante exploratória: texto com acentos e caixa originais")
    parser.add_argument("--saida", type=Path, default=SAIDA_PADRAO)
    args = parser.parse_args()
    imprimir(rodar(args.modelos, normalizar_texto=not args.texto_original, saida=args.saida))
    print(f"\nRelatório: {args.saida}")


if __name__ == "__main__":
    main()
