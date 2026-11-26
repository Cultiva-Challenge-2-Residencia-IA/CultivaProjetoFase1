"""Relevância da busca (issue #105), pelos critérios de eval/relevancia/criterios.md.

    uv run python -m src.evaluation.relevancia busca --split dev [--modelos M1 M2]
    uv run python -m src.evaluation.relevancia filtro --split dev [--limiar 0.1]
    uv run python -m src.evaluation.relevancia reformulacao --split dev     # exige o Ollama
    uv run python -m src.evaluation.relevancia hyde --split dev             # exige o Ollama
    uv run python -m src.evaluation.relevancia roteamento --split dev
    uv run python -m src.evaluation.relevancia latencia --split dev         # usa o resultado do hyde

Grava `eval/relevancia/resultado_<medida>_<split>.json`. O `test` roda uma vez, depois das decisões.
"""

import argparse
import copy
import json
from pathlib import Path
import re
import statistics
import time
from typing import Any, Callable, Dict, List, Optional, Sequence

from src.config import CORPUS_RAG_DIR_SAUDE_FISICA, RERANKER_CANDIDATOS
from src.evaluation.benchmark_v2 import carregar_casos, metricas_de_recuperacao
from src.models.schemas import RetrievedChunk
from src.rag.corpus_loader import carregar_chunks_do_corpus
from src.retrieval.hybrid_retriever import HybridRetriever
from src.retrieval.reranker_cruzado import RerankerCruzado

RAIZ = Path(__file__).resolve().parents[2]
DIR = RAIZ / "eval" / "relevancia"
K = 4
MODELOS_CANDIDATOS = ["BAAI/bge-reranker-v2-m3", "jinaai/jina-reranker-v2-base-multilingual"]


def _json(caminho: Path) -> Any:
    return json.loads(caminho.read_text(encoding="utf-8"))


def _casos(nome: str, split: str) -> List[Dict[str, Any]]:
    return [c for c in _json(DIR / f"{nome}.json")["casos"] if c["split"] == split]


def _salvar(medida: str, split: str, dados: Dict[str, Any]) -> None:
    caminho = DIR / f"resultado_{medida}_{split}.json"
    caminho.write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"gravado: {caminho.relative_to(RAIZ)}")


def fonte_do_trecho(chunk_id: str) -> str:
    return re.sub(r"-(p[0-9]{3}|s[0-9]{3}|resumo)-[0-9]{2}$", "", chunk_id)


def metricas_por_fonte(recuperados: Sequence[str], esperadas: Sequence[str], k: int = K) -> Dict[str, float]:
    fontes = [fonte_do_trecho(t) for t in recuperados[:k]]
    rr = next((1.0 / i for i, f in enumerate(fontes, 1) if f in esperadas), 0.0)
    return {"acerto": float(rr > 0), "rr": rr}


# --- Conjuntos ---------------------------------------------------------------------------------

def casos_nutricao(split: str) -> List[Dict[str, Any]]:
    """Casos `responder` do golden v2 com Trechos julgados (notas >= 1 contam como relevantes)."""
    casos = []
    for caso in carregar_casos():
        evid = (caso.get("recuperacao") or {}).get("evidencias") or {}
        if caso["split"] == split and caso.get("comportamento_esperado") == "responder" and evid:
            casos.append({"id": caso["id"], "pergunta": caso["pergunta"],
                          "notas": {tid: int(v["nota"]) for tid, v in evid.items()}})
    return casos


def casos_saude_fisica(split: str) -> List[Dict[str, Any]]:
    return _casos("busca_saude_fisica", split)


def casos_saude_fisica_99(split: str) -> List[Dict[str, Any]]:
    dados = _json(RAIZ / "eval" / "multiagentes" / "golden_saude_fisica.json")
    return [c for c in dados["casos"] if c["split"] == split]


def casos_dentro_abstencao(split: str) -> List[Dict[str, Any]]:
    dados = _json(RAIZ / "eval" / "abstencao" / "casos.json")
    casos = dados["casos"] if isinstance(dados, dict) else dados
    return [c for c in casos if c.get("split") == split and c.get("tipo") == "dentro"]


# --- Índices -----------------------------------------------------------------------------------

_INDICES: Dict[str, HybridRetriever] = {}


def indice(area: str) -> HybridRetriever:
    """Busca híbrida da área como no produto (sem reranker), construída uma vez por execução."""
    if area not in _INDICES:
        if area == "nutricao":
            chunks = carregar_chunks_do_corpus()
        else:
            chunks = carregar_chunks_do_corpus(rag_dir=CORPUS_RAG_DIR_SAUDE_FISICA)
        _INDICES[area] = HybridRetriever(chunks)
    return _INDICES[area]


def com_reranker(base: HybridRetriever, reranker: Optional[RerankerCruzado],
                 candidatos: int = RERANKER_CANDIDATOS) -> HybridRetriever:
    """Mesmo índice, com ou sem o reranker (cópia rasa: BM25 e ChromaDB são compartilhados)."""
    copia = copy.copy(base)
    copia.reranker = reranker
    copia.candidatos_reranker = candidatos
    if reranker is not None:
        copia.top_k_bm25 = max(base.top_k_bm25, candidatos)
        copia.top_k_vector = max(base.top_k_vector, candidatos)
    return copia


def _medir_lista(buscar: Callable[[str], List[RetrievedChunk]], casos: List[Dict[str, Any]],
                 avaliar: Callable[[Dict[str, Any], List[str]], Dict[str, float]]) -> Dict[str, Any]:
    linhas, tempos = [], []
    for caso in casos:
        inicio = time.perf_counter()
        recuperados = buscar(caso["pergunta"])
        tempos.append(time.perf_counter() - inicio)
        ids = [r.chunk.chunk_id for r in recuperados]
        linhas.append({"id": caso["id"], "recuperados": ids, **avaliar(caso, ids)})
    metricas = [m for m in linhas[0] if m not in ("id", "recuperados")] if linhas else []
    resumo = {m: round(statistics.mean(ln[m] for ln in linhas), 3) for m in metricas}
    resumo["n"] = len(linhas)
    if tempos:
        ordenados = sorted(tempos)
        resumo["segundos_mediana"] = round(statistics.median(ordenados), 3)
        resumo["segundos_p95"] = round(ordenados[min(len(ordenados) - 1, int(0.95 * len(ordenados)))], 3)
    return {"resumo": resumo, "casos": linhas}


def _avaliar_nutricao(caso, ids):
    m = metricas_de_recuperacao(caso["notas"], ids, K)
    return {"rr": m["rr_trecho"], "recall": m["recall_trecho"]}


def _avaliar_fonte(caso, ids):
    return metricas_por_fonte(ids, caso["fontes_esperadas"])


def medir_busca(split: str, modelos: Sequence[str]) -> None:
    conjuntos = {
        "nutricao": ("nutricao", casos_nutricao(split), _avaliar_nutricao),
        "saude_fisica": ("saude_fisica", casos_saude_fisica(split), _avaliar_fonte),
        "saude_fisica_99_ja_visto": ("saude_fisica", casos_saude_fisica_99(split), _avaliar_fonte),
    }
    resultado: Dict[str, Any] = {"split": split, "k": K, "candidatos": RERANKER_CANDIDATOS, "configuracoes": {}}
    configuracoes: Dict[str, Optional[RerankerCruzado]] = {"base": None}
    configuracoes.update({m: RerankerCruzado(m) for m in modelos})
    for nome, reranker in configuracoes.items():
        por_conjunto = {}
        for conjunto, (area, casos, avaliar) in conjuntos.items():
            retriever = com_reranker(indice(area), reranker)
            if reranker is not None and casos:
                retriever.retrieve(casos[0]["pergunta"], top_k=K)  # carrega o modelo fora do tempo
            por_conjunto[conjunto] = _medir_lista(lambda q: retriever.retrieve(q, top_k=K), casos, avaliar)
        resultado["configuracoes"][nome] = por_conjunto
        print(nome, json.dumps({c: v["resumo"] for c, v in por_conjunto.items()}, ensure_ascii=False))
    _salvar("busca", split, resultado)


# --- Filtro de relevância ----------------------------------------------------------------------

def _notas_dos_casos(area: str, casos: List[Dict[str, Any]], reranker_busca: Optional[RerankerCruzado],
                     filtro: RerankerCruzado, chave: str = "pergunta") -> List[Dict[str, Any]]:
    """Busca de cada caso como no produto e a nota do filtro de cada Trecho do top-K."""
    retriever = com_reranker(indice(area), reranker_busca)
    linhas = []
    for caso in casos:
        recuperados = retriever.retrieve(caso[chave], top_k=K)
        notas = filtro.pontuar(caso[chave], [r.chunk.contextualized_text for r in recuperados],
                               [r.chunk.chunk_id for r in recuperados])
        linha = {"id": caso["id"], "area": area, "pergunta": caso[chave],
                 "trechos": [r.chunk.chunk_id for r in recuperados], "notas": [round(n, 6) for n in notas]}
        for extra in ("notas_julgadas", "fontes_esperadas"):
            if extra in caso:
                linha[extra] = caso[extra]
        linhas.append(linha)
    return linhas


def _lacuna(linha: Dict[str, Any], limiar: float) -> bool:
    return not any(n >= limiar for n in linha["notas"])


def _recall_apos_filtro(linha: Dict[str, Any], limiar: float) -> Dict[str, float]:
    mantidos = [t for t, n in zip(linha["trechos"], linha["notas"]) if n >= limiar]
    antes = metricas_de_recuperacao(linha["notas_julgadas"], linha["trechos"], K)["recall_trecho"]
    depois = metricas_de_recuperacao(linha["notas_julgadas"], mantidos, K)["recall_trecho"]
    return {"antes": antes, "depois": depois}


def calibrar_limiar(controles: List[Dict[str, Any]], tolerancia: float = 0.05) -> float:
    """Maior τ com lacuna indevida de no máximo `tolerancia` nos controles com base."""
    maximos = sorted(max(ln["notas"]) if ln["notas"] else 0.0 for ln in controles)
    permitidos = int(tolerancia * len(maximos))  # casos com base que podem ficar abaixo de τ
    # τ = a nota máxima do (permitidos+1)-ésimo menor caso: só os `permitidos` menores ficam abaixo.
    return maximos[permitidos] if maximos else 0.0


def medir_filtro(split: str, limiar: Optional[float], areas_com_reranker: Sequence[str], modelo: str) -> None:
    filtro = RerankerCruzado(modelo)
    reranker = {a: (filtro if a in areas_com_reranker else None) for a in ("nutricao", "saude_fisica")}
    nutricao = [{**c, "notas_julgadas": c["notas"]} for c in casos_nutricao(split)]
    for c in nutricao:
        del c["notas"]
    controles = {
        "golden_saude_fisica": _notas_dos_casos("saude_fisica", casos_saude_fisica(split), reranker["saude_fisica"], filtro),
        "golden_v2_nutricao": _notas_dos_casos("nutricao", nutricao, reranker["nutricao"], filtro),
        "abstencao_dentro": _notas_dos_casos("nutricao", casos_dentro_abstencao(split), reranker["nutricao"], filtro),
    }
    sem_base = []
    for area in ("nutricao", "saude_fisica"):
        casos = [c for c in _casos("sem_base", split) if c["area"] == area]
        sem_base += _notas_dos_casos(area, casos, reranker[area], filtro)
    todos_controles = [ln for grupo in controles.values() for ln in grupo]
    calibrado = calibrar_limiar(todos_controles)
    if limiar is None:
        if split != "dev":
            raise SystemExit("No test, passe o --limiar escolhido no dev.")
        limiar = calibrado
    resumo: Dict[str, Any] = {"modelo": modelo, "reranker_na_busca": list(areas_com_reranker),
                              "limiar": round(limiar, 6), "limiar_calibrado_neste_split": round(calibrado, 6)}
    for nome, grupo in controles.items():
        resumo[f"lacuna_indevida_{nome}"] = round(sum(_lacuna(ln, limiar) for ln in grupo) / len(grupo), 3)
    resumo["lacuna_indevida_controles"] = round(
        sum(_lacuna(ln, limiar) for ln in todos_controles) / len(todos_controles), 3)
    for area in ("nutricao", "saude_fisica"):
        grupo = [ln for ln in sem_base if ln["area"] == area]
        resumo[f"lacuna_sem_base_{area}"] = round(sum(_lacuna(ln, limiar) for ln in grupo) / len(grupo), 3)
    resumo["lacuna_sem_base"] = round(sum(_lacuna(ln, limiar) for ln in sem_base) / len(sem_base), 3)
    recalls = [_recall_apos_filtro(ln, limiar) for ln in controles["golden_v2_nutricao"]]
    resumo["recall_nutricao_sem_filtro"] = round(statistics.mean(r["antes"] for r in recalls), 3)
    resumo["recall_nutricao_com_filtro"] = round(statistics.mean(r["depois"] for r in recalls), 3)
    descartados = [n < limiar for grupo in controles.values() for ln in grupo for n in ln["notas"]]
    resumo["trechos_descartados_nos_controles"] = round(sum(descartados) / len(descartados), 3)
    print(json.dumps(resumo, ensure_ascii=False, indent=1))
    for ln in sem_base:
        if not _lacuna(ln, limiar):
            print(f"  SEM LACUNA {ln['id']} ({max(ln['notas']):.3f}): {ln['pergunta']}")
    for ln in todos_controles:
        if _lacuna(ln, limiar):
            print(f"  LACUNA INDEVIDA {ln['id']} ({max(ln['notas']):.3f}): {ln['pergunta']}")
    _salvar("filtro", split, {"resumo": resumo, "controles": controles, "sem_base": sem_base})


# --- Com o LLM: reformulação e HyDE ------------------------------------------------------------

def _llm():
    from src.agent.llm_json import ClienteJsonOllama

    cliente = ClienteJsonOllama("avaliacao_relevancia")
    if not cliente.disponivel():
        raise SystemExit("Ollama indisponível: esta medida exige o LLM local.")
    return cliente


def _buscar_fundido(retriever: HybridRetriever, consultas: Sequence[str]) -> List[RetrievedChunk]:
    from src.retrieval.fusao import fundir_rrf

    listas = [retriever.retrieve(c, top_k=K) for c in consultas]
    return listas[0] if len(listas) == 1 else fundir_rrf(listas, top_k=K)


def medir_reformulacao(split: str, limiar: float, areas_com_reranker: Sequence[str], modelo: str) -> None:
    """Casos em lacuna no filtro (controles com base e sem base): a reformulação os tira dela?"""
    from src.rag.relevancia import julgar, reformular

    llm = _llm()
    filtro = RerankerCruzado(modelo)
    dados = _json(DIR / f"resultado_filtro_{split}.json")
    grupos = {"controles": [ln for g in dados["controles"].values() for ln in g], "sem_base": dados["sem_base"]}
    resultado: Dict[str, Any] = {"modelo_llm": llm.modelo, "limiar": limiar, "grupos": {}}
    for nome, linhas in grupos.items():
        casos = []
        for ln in linhas:
            if not _lacuna(ln, limiar):
                continue
            area = ln["area"]
            retriever = com_reranker(indice(area), filtro if area in areas_com_reranker else None)
            inicio = time.perf_counter()
            consultas = reformular(ln["pergunta"], area, llm)
            julgamento = julgar(ln["pergunta"], _buscar_fundido(retriever, consultas), filtro, limiar) if consultas else None
            casos.append({"id": ln["id"], "area": area, "pergunta": ln["pergunta"], "consultas": consultas,
                          "segundos": round(time.perf_counter() - inicio, 2),
                          "saiu_da_lacuna": bool(julgamento and not julgamento.lacuna),
                          "mantidos": [r.chunk.chunk_id for r in julgamento.mantidos] if julgamento else []})
        resultado["grupos"][nome] = {"em_lacuna_antes": len(casos), "n_total": len(linhas),
                                     "sairam_da_lacuna": sum(c["saiu_da_lacuna"] for c in casos), "casos": casos}
    sem_base = resultado["grupos"]["sem_base"]
    resultado["lacuna_sem_base_depois"] = round(
        (sem_base["em_lacuna_antes"] - sem_base["sairam_da_lacuna"]) / sem_base["n_total"], 3)
    print(json.dumps({k: (v if k != "grupos" else {g: {x: y for x, y in d.items() if x != "casos"}
                                                    for g, d in v.items()}) for k, v in resultado.items()},
                     ensure_ascii=False, indent=1))
    _salvar("reformulacao", split, resultado)


def medir_hyde(split: str, areas_com_reranker: Sequence[str], modelo: str) -> None:
    """Golden novo de Saúde Física: a busca do produto sem e com o trecho hipotético da reescrita."""
    from src.orquestrador.reescrita import reescrever

    llm = _llm()
    reranker = RerankerCruzado(modelo) if "saude_fisica" in areas_com_reranker else None
    retriever = com_reranker(indice("saude_fisica"), reranker)
    linhas = []
    for caso in casos_saude_fisica(split):
        reescrita = reescrever(caso["pergunta"], [], llm)
        sub = next((s for s in reescrita.subperguntas if s.area == "saude_fisica"), None)
        extras = [sub.trecho_hipotetico] if sub and sub.trecho_hipotetico else []
        if extras and reescrita.pergunta_completa.strip() != (sub.texto or "").strip():
            extras.append(reescrita.pergunta_completa)
        base = [r.chunk.chunk_id for r in retriever.retrieve(caso["pergunta"], top_k=K)]
        com = [r.chunk.chunk_id for r in _buscar_fundido(retriever, [caso["pergunta"]] + extras)]
        linhas.append({"id": caso["id"], "extras": extras,
                       "base": metricas_por_fonte(base, caso["fontes_esperadas"]),
                       "hyde": metricas_por_fonte(com, caso["fontes_esperadas"])})
    resumo = {"modelo_llm": llm.modelo, "reranker_na_busca": reranker is not None, "n": len(linhas)}
    for m in ("rr", "acerto"):
        b = statistics.mean(ln["base"][m] for ln in linhas)
        h = statistics.mean(ln["hyde"][m] for ln in linhas)
        resumo[m] = {"base": round(b, 3), "hyde": round(h, 3), "diferenca": round(h - b, 3)}
    print(json.dumps(resumo, ensure_ascii=False, indent=1))
    _salvar("hyde", split, {"resumo": resumo, "casos": linhas})


def _acerto_roteamento(casos: List[Dict[str, Any]], chave_mensagem: str = "mensagem") -> Dict[str, Any]:
    from src.evaluation.multiagentes import areas_previstas

    linhas = []
    for caso in casos:
        previstas = areas_previstas(caso[chave_mensagem], None)
        linhas.append({"id": caso["id"], "tipo": caso.get("tipo", "composta"), "mensagem": caso[chave_mensagem],
                       "esperadas": sorted(caso["areas_esperadas"]), "previstas": previstas,
                       "acerto": previstas == sorted(caso["areas_esperadas"])})
    por_tipo = {}
    for tipo in sorted({ln["tipo"] for ln in linhas}):
        grupo = [ln for ln in linhas if ln["tipo"] == tipo]
        por_tipo[tipo] = {"n": len(grupo), "acerto": round(sum(ln["acerto"] for ln in grupo) / len(grupo), 3)}
    resumo = {"n": len(linhas), "acerto": round(sum(ln["acerto"] for ln in linhas) / max(1, len(linhas)), 3),
              "por_tipo": por_tipo}
    return {"resumo": resumo, "casos": linhas}


def medir_roteamento(split: str) -> None:
    """Só as regras (o que o CI mede): casos novos do split e, como regressão, todos os da #99."""
    multi = RAIZ / "eval" / "multiagentes"
    resultado = {
        "configuracao": "regras",
        "novos": _acerto_roteamento(_casos("roteamento", split)),
        "issue_99_roteamento_ja_visto": _acerto_roteamento(_json(multi / "roteamento.json")["casos"]),
        "issue_99_compostas_ja_visto": _acerto_roteamento(_json(multi / "compostas.json")["casos"]),
    }
    for nome, bloco in resultado.items():
        if nome == "configuracao":
            continue
        print(nome, json.dumps(bloco["resumo"], ensure_ascii=False))
        for ln in bloco["casos"]:
            if not ln["acerto"]:
                print(f"  ERRO {ln['id']}: esperado {ln['esperadas']}, previsto {ln['previstas']} | {ln['mensagem']}")
    _salvar("roteamento", split, resultado)


def _p95(valores: Sequence[float]) -> float:
    ordenados = sorted(valores)
    return ordenados[min(len(ordenados) - 1, round(0.95 * (len(ordenados) - 1)))]


def medir_latencia(split: str) -> None:
    """Latência do Agente de Saúde Física sem e com as consultas extras do HyDE.

    Usa os trechos hipotéticos gravados por `hyde` (sem chamar o LLM) e a configuração padrão do
    agente: reranker na busca, filtro de relevância e síntese extrativa. O cache do reranker é
    limpo antes de cada medida, como numa pergunta nova. Não inclui a chamada de reescrita do Chat.
    """
    from src.agents.fisica.consultor import ConsultorSaudeFisica

    perguntas = {c["id"]: c["pergunta"] for c in casos_saude_fisica(split)}
    hyde = _json(DIR / f"resultado_hyde_{split}.json")["casos"]
    consultor = ConsultorSaudeFisica(enable_ollama=False)
    if consultor.retriever.reranker is None:
        raise SystemExit("O reranker de Saúde Física está desligado (CULTIVA_RERANKER_SAUDE_FISICA).")
    consultor.responder("aquecimento antes do treino", K, [], [])  # carrega o modelo
    tempos: Dict[str, List[float]] = {"sem_extras": [], "com_extras_hyde": []}
    for caso in hyde:
        for nome, extras in (("sem_extras", []), ("com_extras_hyde", caso["extras"])):
            consultor.retriever.reranker._cache.clear()
            inicio = time.perf_counter()
            consultor.responder(perguntas[caso["id"]], K, extras, [])
            tempos[nome].append(time.perf_counter() - inicio)
    resumo = {nome: {"n": len(v), "mediana_s": round(statistics.median(v), 3), "p95_s": round(_p95(v), 3)}
              for nome, v in tempos.items()}
    print(json.dumps(resumo, ensure_ascii=False, indent=1))
    _salvar("latencia", split, {"resumo": resumo, "tempos_s": {k: [round(t, 3) for t in v] for k, v in tempos.items()}})


def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("medida", choices=["busca", "filtro", "reformulacao", "hyde", "roteamento", "latencia"])
    parser.add_argument("--split", choices=["dev", "test"], default="dev")
    parser.add_argument("--modelos", nargs="+", default=MODELOS_CANDIDATOS)
    parser.add_argument("--modelo", default=MODELOS_CANDIDATOS[0], help="filtro: cross-encoder do filtro")
    parser.add_argument("--limiar", type=float, default=None, help="filtro: τ escolhido no dev (obrigatório no test)")
    parser.add_argument("--reranker-em", nargs="*", default=[], choices=["nutricao", "saude_fisica"],
                        help="filtro: áreas com o reranker ligado na busca")
    args = parser.parse_args(argv)
    if args.medida == "busca":
        medir_busca(args.split, args.modelos)
    elif args.medida == "filtro":
        medir_filtro(args.split, args.limiar, args.reranker_em, args.modelo)
    elif args.medida == "reformulacao":
        if args.limiar is None:
            raise SystemExit("Passe o --limiar escolhido no dev.")
        medir_reformulacao(args.split, args.limiar, args.reranker_em, args.modelo)
    elif args.medida == "hyde":
        medir_hyde(args.split, args.reranker_em, args.modelo)
    elif args.medida == "roteamento":
        medir_roteamento(args.split)
    elif args.medida == "latencia":
        medir_latencia(args.split)


if __name__ == "__main__":
    main()
