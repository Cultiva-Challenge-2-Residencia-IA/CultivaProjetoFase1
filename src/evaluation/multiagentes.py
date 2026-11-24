"""Avaliação do sistema multiagentes (issue #99), pelos critérios de eval/multiagentes/criterios.md.

    uv run python -m src.evaluation.multiagentes roteamento --split dev [--sem-llm]
    uv run python -m src.evaluation.multiagentes busca --split dev
    uv run python -m src.evaluation.multiagentes continuacao --split dev
    uv run python -m src.evaluation.multiagentes compostas --split dev

Exige o Ollama local (ADR 0004), exceto `roteamento --sem-llm`. Grava
`eval/multiagentes/resultado_<medida>_<split>.json`. O `test` roda uma vez, depois das decisões.
"""

import argparse
import json
from pathlib import Path
import statistics
import tempfile
import time
from typing import Any, Dict, List, Optional

from src.agent.llm_json import ClienteJsonOllama
from src.chat.historico import HistoricoSQLite
from src.chat.servico import CHAT_GERAL, ServicoDeChat
from src.evaluation.benchmark_v2 import carregar_casos, metricas_de_recuperacao
from src.orquestrador.reescrita import Mensagem, reescrever
from src.orquestrador.roteamento import AREA_NUTRICAO, AREA_SAUDE_FISICA, rotear_por_regras
from src.retrieval.fusao import fundir_rrf
from src.retrieval.hybrid_retriever import normalize_text

DIR = Path(__file__).resolve().parents[2] / "eval" / "multiagentes"
K = 4


def _casos(nome: str, split: str) -> List[Dict[str, Any]]:
    dados = json.loads((DIR / f"{nome}.json").read_text(encoding="utf-8"))
    return [c for c in dados["casos"] if c["split"] == split]


def _salvar(medida: str, split: str, dados: Dict[str, Any]) -> None:
    caminho = DIR / f"resultado_{medida}_{split}.json"
    caminho.write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"gravado: {caminho.relative_to(DIR.parents[1])}")


def _llm() -> ClienteJsonOllama:
    cliente = ClienteJsonOllama("avaliacao_multiagentes")
    if not cliente.disponivel():
        raise SystemExit("Ollama indisponível: esta medida exige o LLM local.")
    return cliente


def areas_previstas(mensagem: str, llm: Optional[ClienteJsonOllama]) -> List[str]:
    """Mesma decisão do Chat geral (`ServicoDeChat._rotear`), sem chamar os agentes."""
    servico = ServicoDeChat(agentes={}, historico=None, llm=llm)
    reescrita, regras, subperguntas = servico._rotear(CHAT_GERAL, mensagem, [])
    if not subperguntas:
        if regras.estudos or reescrita.origem == "llm":
            return []
        return [AREA_NUTRICAO]  # sem LLM e sem termo: o Agente de Nutrição, como antes
    return sorted(s.area for s in subperguntas)


def medir_roteamento(split: str, sem_llm: bool) -> None:
    llm = None if sem_llm else _llm()
    linhas = []
    for caso in _casos("roteamento", split):
        previstas = areas_previstas(caso["mensagem"], llm)
        linhas.append({**caso, "previstas": previstas, "acerto": previstas == sorted(caso["areas_esperadas"]),
                       "regras": sorted(rotear_por_regras(caso["mensagem"]).areas)})
    por_tipo = {}
    for tipo in sorted({c["tipo"] for c in linhas}):
        grupo = [c for c in linhas if c["tipo"] == tipo]
        por_tipo[tipo] = {"n": len(grupo), "acerto": round(sum(c["acerto"] for c in grupo) / len(grupo), 3)}
    resumo = {"configuracao": "regras" if sem_llm else "regras+llm", "n": len(linhas),
              "acerto": round(sum(c["acerto"] for c in linhas) / len(linhas), 3), "por_tipo": por_tipo}
    print(json.dumps(resumo, ensure_ascii=False))
    for c in linhas:
        if not c["acerto"]:
            print(f"  ERRO {c['id']}: esperado {c['areas_esperadas']}, previsto {c['previstas']} | {c['mensagem']}")
    _salvar(f"roteamento_{'regras' if sem_llm else 'llm'}", split, {"resumo": resumo, "casos": linhas})


def _buscar(retriever, consultas: List[str]) -> List[str]:
    listas = [retriever.retrieve(c, top_k=K) for c in consultas]
    fundidos = listas[0] if len(listas) == 1 else fundir_rrf(listas, top_k=K)
    return [r.chunk.chunk_id for r in fundidos]


def _consultas_com_reescrita(pergunta: str, area: str, llm) -> List[str]:
    reescrita = reescrever(pergunta, [], llm)
    sub = next((s for s in reescrita.subperguntas if s.area == area), None)
    consultas = [pergunta]
    if sub is not None:
        consultas += [c for c in (sub.trecho_hipotetico, sub.texto if sub.texto != pergunta else None) if c]
    return consultas


def _rr_fonte(recuperados: List[str], esperadas: List[str]) -> Dict[str, float]:
    import re

    fontes = [re.sub(r"-(p[0-9]{3}|s[0-9]{3}|resumo)-[0-9]{2}$", "", t) for t in recuperados[:K]]
    rr = next((1.0 / i for i, f in enumerate(fontes, 1) if f in esperadas), 0.0)
    return {"acerto_fonte": float(rr > 0), "rr_fonte": rr}


def medir_busca(split: str) -> None:
    from src.agent.consultant_baseline import NutritionConsultantBaseline
    from src.agents.fisica.consultor import ConsultorSaudeFisica

    llm = _llm()
    resultado: Dict[str, Any] = {}
    nutricao = NutritionConsultantBaseline(enable_ollama=False)
    linhas = []
    for caso in carregar_casos():
        evid = (caso.get("recuperacao") or {}).get("evidencias") or {}
        if caso["split"] != split or caso.get("comportamento_esperado") != "responder" or not evid:
            continue
        notas = {tid: int(v["nota"]) for tid, v in evid.items()}
        base = metricas_de_recuperacao(notas, _buscar(nutricao.retriever, [caso["pergunta"]]), K)
        consultas = _consultas_com_reescrita(caso["pergunta"], AREA_NUTRICAO, llm)
        com = metricas_de_recuperacao(notas, _buscar(nutricao.retriever, consultas), K)
        linhas.append({"id": caso["id"], "consultas": consultas,
                       "base": {"rr": base["rr_trecho"], "recall": base["recall_trecho"]},
                       "reescrita": {"rr": com["rr_trecho"], "recall": com["recall_trecho"]}})
    resultado["nutricao"] = _resumo_busca(linhas, ("rr", "recall"))

    fisica = ConsultorSaudeFisica(enable_ollama=False)
    linhas_sf = []
    for caso in _casos("golden_saude_fisica", split):
        base = _rr_fonte(_buscar(fisica.retriever, [caso["pergunta"]]), caso["fontes_esperadas"])
        consultas = _consultas_com_reescrita(caso["pergunta"], AREA_SAUDE_FISICA, llm)
        com = _rr_fonte(_buscar(fisica.retriever, consultas), caso["fontes_esperadas"])
        linhas_sf.append({"id": caso["id"], "consultas": consultas,
                          "base": {"rr": base["rr_fonte"], "acerto": base["acerto_fonte"]},
                          "reescrita": {"rr": com["rr_fonte"], "acerto": com["acerto_fonte"]}})
    resultado["saude_fisica"] = _resumo_busca(linhas_sf, ("rr", "acerto"))
    print(json.dumps({k: v["resumo"] for k, v in resultado.items()}, ensure_ascii=False, indent=1))
    _salvar("busca", split, resultado)


def _resumo_busca(linhas: List[Dict[str, Any]], metricas) -> Dict[str, Any]:
    resumo: Dict[str, Any] = {"n": len(linhas)}
    for m in metricas:
        b = [ln["base"][m] for ln in linhas]
        r = [ln["reescrita"][m] for ln in linhas]
        resumo[m] = {"base": round(statistics.mean(b), 3) if b else None,
                     "reescrita": round(statistics.mean(r), 3) if r else None,
                     "diferenca": round(statistics.mean(r) - statistics.mean(b), 3) if b else None}
    return {"resumo": resumo, "casos": linhas}


def medir_continuacao(split: str) -> None:
    llm = _llm()
    linhas = []
    for caso in _casos("continuacao", split):
        historico = [Mensagem("usuario", caso["anterior"])]
        reescrita = reescrever(caso["mensagem"], historico, llm)
        termo_ok = caso["termo_esperado"] in normalize_text(reescrita.pergunta_completa)
        area_ok = caso["area_esperada"] in reescrita.areas
        linhas.append({**caso, "pergunta_completa": reescrita.pergunta_completa, "areas": reescrita.areas,
                       "origem": reescrita.origem, "acerto": termo_ok and area_ok})
    resumo = {"n": len(linhas), "acerto": round(sum(c["acerto"] for c in linhas) / max(1, len(linhas)), 3)}
    print(json.dumps(resumo, ensure_ascii=False))
    for c in linhas:
        print(f"  {'ok ' if c['acerto'] else 'ERRO'} {c['id']}: {c['pergunta_completa']} {c['areas']}")
    _salvar("continuacao", split, {"resumo": resumo, "casos": linhas})


def medir_compostas(split: str) -> None:
    from src.chat.fabrica import criar_servico

    with tempfile.TemporaryDirectory() as pasta:
        servico = criar_servico(enable_ollama=True, historico=HistoricoSQLite(Path(pasta) / "h.sqlite3"))
        if servico.llm is None:
            raise SystemExit("Ollama indisponível: esta medida exige o LLM local.")
        linhas = []
        for caso in _casos("compostas", split):
            inicio = time.perf_counter()
            resposta = servico.enviar(CHAT_GERAL, "avaliacao", f"c-{caso['id']}", caso["mensagem"])
            linhas.append({"id": caso["id"], "mensagem": caso["mensagem"], "areas": sorted(resposta.areas),
                           "duas_areas": sorted(resposta.areas) == sorted(caso["areas_esperadas"]),
                           "modo": resposta.modo_sincronizacao, "tipo": resposta.tipo,
                           "segundos": round(time.perf_counter() - inicio, 1), "texto": resposta.texto})
            print(f"  {caso['id']}: {linhas[-1]['areas']} {linhas[-1]['modo']} ({linhas[-1]['segundos']} s)")
    n = len(linhas)
    resumo = {"n": n, "duas_areas": round(sum(c["duas_areas"] for c in linhas) / n, 3),
              "integrada": round(sum(c["modo"] == "integrada" for c in linhas) / n, 3),
              "mediana_segundos": statistics.median(c["segundos"] for c in linhas)}
    print(json.dumps(resumo, ensure_ascii=False))
    _salvar("compostas", split, {"resumo": resumo, "casos": linhas})


def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("medida", choices=["roteamento", "busca", "continuacao", "compostas"])
    parser.add_argument("--split", choices=["dev", "test"], default="dev")
    parser.add_argument("--sem-llm", action="store_true", help="Só roteamento: só as regras (o que o CI mede)")
    args = parser.parse_args(argv)
    if args.medida == "roteamento":
        medir_roteamento(args.split, args.sem_llm)
    elif args.medida == "busca":
        medir_busca(args.split)
    elif args.medida == "continuacao":
        medir_continuacao(args.split)
    else:
        medir_compostas(args.split)


if __name__ == "__main__":
    main()
