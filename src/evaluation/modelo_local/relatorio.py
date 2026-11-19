"""Agrega as gerações, o juiz e as ferramentas no relatório da issue #55."""

from __future__ import annotations

import json
import statistics
from typing import Any, Dict, List, Optional

from src.evaluation.modelo_local import config, ferramentas
from src.evaluation.modelo_local.entradas import carregar
from src.evaluation.modelo_local.geracao import arquivo_do_modelo, ler_jsonl
from src.evaluation.modelo_local.juiz import amostra_do_juiz, contexto_do_caso
from src.evaluation.modelo_local.metricas import (
    TIPOS_DE_SEGURANCA,
    bootstrap_pareado,
    cobertura_termos,
    imperativos_prescritivos,
    percentil,
    rouge_l,
    texto_completo,
)

# Eliminatórias registradas na issue #55.
JSON_MINIMO = 0.99


def _media(valores: List[Optional[float]]) -> Optional[float]:
    validos = [v for v in valores if v is not None]
    return round(sum(validos) / len(validos), 4) if validos else None


def _por_caso(linhas: List[Dict[str, Any]], campo: str) -> Dict[str, float]:
    """Média por caso (sobre as sementes), para o teste pareado."""
    grupos: Dict[str, List[float]] = {}
    for linha in linhas:
        if linha.get(campo) is not None:
            grupos.setdefault(linha["id"], []).append(float(linha[campo]))
    return {k: sum(v) / len(v) for k, v in grupos.items()}


def avaliar_modelo(modelo: str, casos: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    geracoes = ler_jsonl(arquivo_do_modelo(modelo))
    # Só a amostra conta, para que todos os candidatos sejam julgados nos mesmos casos.
    amostra = set(amostra_do_juiz(list(casos.values())))
    julgamentos = {(j["id"], j["semente"]): j for j in ler_jsonl(arquivo_do_modelo(modelo, "juiz"))
                   if j["id"] in amostra}
    bert = {(b["id"], b["semente"]): b for b in ler_jsonl(arquivo_do_modelo(modelo, "bertscore"))}
    linhas = []
    for g in geracoes:
        caso = casos.get(g["id"])
        if caso is None:
            continue
        linha: Dict[str, Any] = {"id": g["id"], "semente": g["semente"], "tipo": caso["tipo"],
                                 "erro": g.get("erro"), "json_valido": g.get("json_valido", False),
                                 "esquema_valido": g.get("esquema_valido", False), "truncada": g.get("truncada", False),
                                 "segundos": None if g.get("maquina") else g.get("segundos"),
                                 "maquina": g.get("maquina")}
        if g.get("tokens_saida") and g.get("duracao_saida_ns") and not g.get("maquina"):
            linha["tokens_por_segundo"] = g["tokens_saida"] / (g["duracao_saida_ns"] / 1e9)
        saida = None
        if g.get("json_valido"):
            try:
                saida = json.loads(g["conteudo"])
            except (json.JSONDecodeError, TypeError):
                saida = None
        if isinstance(saida, dict):
            texto = texto_completo(saida)
            linha["cobertura_termos"] = cobertura_termos(caso, saida)
            linha.update(rouge_l(texto, contexto_do_caso(caso)))
            linha["imperativos"] = imperativos_prescritivos(texto)
        linha.update({k: v for k, v in bert.get((g["id"], g["semente"]), {}).items() if k.startswith("bertscore")})
        j = julgamentos.get((g["id"], g["semente"]))
        if j and "erro_juiz" not in j:
            linha["fidelidade"] = j.get("fidelidade")
            linha["prescricao_juiz"] = float(bool(j.get("prescricao_individual")))
        linhas.append(linha)

    seg = [x for x in linhas if x["tipo"] in TIPOS_DE_SEGURANCA]
    prescricoes = [x for x in seg if x.get("imperativos") or x.get("prescricao_juiz")]
    validas = [x for x in linhas if x["esquema_valido"]]
    tempos = [x["segundos"] for x in linhas if x.get("segundos") and not x.get("erro")]
    info_path = arquivo_do_modelo(modelo, "info").with_suffix(".json")
    info = json.loads(info_path.read_text(encoding="utf-8")) if info_path.exists() else {}
    fer = _ferramentas(modelo)
    resumo = {
        "modelo": modelo,
        "info": info,
        "execucoes": len(linhas),
        "json_valido": _media([float(x["json_valido"]) for x in linhas]),
        "esquema_valido": _media([float(x["esquema_valido"]) for x in linhas]),
        "seguranca_execucoes": len(seg),
        "seguranca_julgadas": sum("prescricao_juiz" in x for x in seg),
        "prescricoes": [{"id": x["id"], "semente": x["semente"], "imperativos": x.get("imperativos"),
                         "juiz": x.get("prescricao_juiz")} for x in prescricoes],
        "fidelidade": _media([x.get("fidelidade") for x in linhas]),
        "fidelidade_julgadas": sum(x.get("fidelidade") is not None for x in linhas),
        "fidelidade_desvio_entre_sementes": _desvio_entre_sementes(linhas, "fidelidade"),
        "cobertura_termos": _media([x.get("cobertura_termos") for x in validas]),
        "rouge_l_precisao": _media([x.get("rouge_l_precisao") for x in validas]),
        "rouge_l_f": _media([x.get("rouge_l_f") for x in validas]),
        "bertscore_precisao": _media([x.get("bertscore_precisao") for x in validas]),
        "bertscore_f": _media([x.get("bertscore_f") for x in validas]),
        "erros": sum(bool(x["erro"]) for x in linhas),
        "timeouts": sum(x["erro"] == "timeout" for x in linhas),
        "truncadas": sum(bool(x["truncada"]) for x in linhas),
        "latencia_p50": percentil(tempos, 0.5),
        "latencia_p95": percentil(tempos, 0.95),
        "tokens_por_segundo": _media([x.get("tokens_por_segundo") for x in linhas]),
        "ferramentas": fer,
    }
    # Prescrição é medida e relatada, mas não elimina: a garantia de RN01 a RN03 fica com o
    # guardrail de saída do consultor (decisão registrada em eval/modelo_local/README.md).
    resumo["sem_prescricao"] = (not prescricoes
                                and {x["id"] for x in seg if "prescricao_juiz" in x} == {x["id"] for x in seg})
    resumo["eliminatorias"] = {
        "json_e_esquema": (resumo["esquema_valido"] or 0) >= JSON_MINIMO,
    }
    resumo["passa"] = all(resumo["eliminatorias"].values())
    semente_1 = [x for x in linhas if x["semente"] == config.SEMENTES_JUIZ_TODOS[0]]
    resumo["fidelidade_semente_1"] = _media([x.get("fidelidade") for x in semente_1])
    resumo["_por_caso"] = {c: _por_caso(linhas, c) for c in ("fidelidade", "cobertura_termos")}
    resumo["_fidelidade_s1"] = _por_caso(semente_1, "fidelidade")
    return resumo


def _desvio_entre_sementes(linhas: List[Dict[str, Any]], campo: str) -> Optional[float]:
    grupos: Dict[str, List[float]] = {}
    for x in linhas:
        if x.get(campo) is not None:
            grupos.setdefault(x["id"], []).append(x[campo])
    desvios = [statistics.pstdev(v) for v in grupos.values() if len(v) > 1]
    return round(sum(desvios) / len(desvios), 4) if desvios else None


def _ferramentas(modelo: str) -> Optional[Dict[str, Any]]:
    linhas = ler_jsonl(arquivo_do_modelo(modelo, "ferramentas"))
    if not linhas:
        return None
    casos = {c["id"]: c for c in ferramentas.carregar_casos()}
    notas = [ferramentas.pontuar(casos[x["id"]], x) for x in linhas if x["id"] in casos]
    return {
        "execucoes": len(notas),
        "sem_suporte": any(x.get("erro") == "sem_suporte_a_ferramentas" for x in linhas),
        "escolha_correta": _media([n.get("escolha_correta") for n in notas]),
        "argumentos_corretos": _media([n.get("argumentos_corretos") for n in notas]),
        "sem_chamada_indevida": _media([n.get("sem_chamada_indevida") for n in notas]),
    }


def classificar(resultados: Dict[str, Dict[str, Any]]) -> tuple[List[str], List[str]]:
    """Ordem da decisão (issue #55): só quem passa na eliminatória de JSON; o líder é o de maior
    fidelidade na semente 1. Quem não é significativamente pior que o líder em fidelidade nem em
    cobertura está empatado com ele, e o empate se resolve pela latência p50 e depois pela VRAM.
    Os demais seguem por fidelidade."""
    aptos = [m for m, r in resultados.items() if r["passa"] and r["fidelidade_semente_1"] is not None]
    if not aptos:
        return [], []
    lider = max(aptos, key=lambda m: (resultados[m]["fidelidade_semente_1"], resultados[m]["cobertura_termos"] or 0))

    def empata(m: str) -> bool:
        if m == lider:
            return True
        for campo, a, b in (("fidelidade", resultados[m]["_fidelidade_s1"], resultados[lider]["_fidelidade_s1"]),
                            ("cobertura_termos", resultados[m]["_por_caso"]["cobertura_termos"],
                             resultados[lider]["_por_caso"]["cobertura_termos"])):
            teste = bootstrap_pareado(a, b)
            if teste and teste["significativa"] and teste["diferenca"] < 0:
                return False
        return True

    empate = [m for m in aptos if empata(m)]
    desempate = sorted(empate, key=lambda m: (resultados[m]["latencia_p50"] or 1e9,
                                              resultados[m]["info"].get("memoria_total_bytes") or 1e18))
    resto = sorted((m for m in aptos if m not in empate), key=lambda m: -resultados[m]["fidelidade_semente_1"])
    return desempate + resto, empate


def montar(modelos: List[str], referencia: str = config.CANDIDATOS[0]) -> Dict[str, Any]:
    casos = {c["id"]: c for c in carregar()}
    resultados = {m: avaliar_modelo(m, casos) for m in modelos if ler_jsonl(arquivo_do_modelo(m))}
    comparacoes = {}
    if referencia in resultados:
        for m, r in resultados.items():
            if m == referencia:
                continue
            comparacoes[m] = {campo: bootstrap_pareado(r["_por_caso"][campo], resultados[referencia]["_por_caso"][campo])
                              for campo in ("fidelidade", "cobertura_termos")}
    classificacao, empate = classificar(resultados)
    finalistas = classificacao[:2]
    entre_finalistas = None
    if len(finalistas) == 2:
        a, b = (resultados[m]["_por_caso"] for m in finalistas)
        entre_finalistas = {campo: bootstrap_pareado(a[campo], b[campo]) for campo in ("fidelidade", "cobertura_termos")}
    for r in resultados.values():
        r.pop("_por_caso")
        r.pop("_fidelidade_s1")
    return {"referencia": referencia, "casos": len(casos), "sementes": config.SEMENTES,
            "classificacao": classificacao, "empatados_com_o_lider": empate,
            "finalistas": finalistas, "entre_finalistas": entre_finalistas,
            "condicoes": {"temperatura": config.TEMPERATURA, "num_ctx": config.NUM_CTX,
                          "num_predict": config.NUM_PREDICT, "think": False, "juiz": config.JUIZ_MODELO},
            "modelos": resultados, "comparacao_com_referencia": comparacoes}


def _fmt(v: Any, pct: bool = True) -> str:
    if v is None:
        return "n/d"
    if isinstance(v, bool):
        return "sim" if v else "não"
    return f"{v * 100:.1f}%" if pct else f"{v:.2f}"


def markdown(rel: Dict[str, Any]) -> str:
    linhas = [
        "# Comparação de modelos locais (issue #55)",
        "",
        "Gerado por `uv run python -m src.evaluation.modelo_local relatorio`. Não edite à mão. Como ler: [`resultados_explicados.md`](resultados_explicados.md).",
        "",
        f"Casos: {rel['casos']} · sementes: {rel['sementes']} · condições: `{json.dumps(rel['condicoes'], ensure_ascii=False)}`",
        "",
        "| Modelo | Passa | JSON e esquema | Prescrição (seg.) | Fidelidade (todas / semente 1) | Cobertura de termos | ROUGE-L prec. | BERTScore prec. | p50 (s) | p95 (s) | tok/s | VRAM (GB) | Ferramentas: escolha / args |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for m, r in rel["modelos"].items():
        vram = r["info"].get("memoria_vram_bytes")
        total = r["info"].get("memoria_total_bytes")
        vram_txt = f"{vram / 1e9:.1f}" + ("" if not total or vram == total else f" de {total / 1e9:.1f}") if vram else "n/d"
        fer = r["ferramentas"] or {}
        linhas.append(
            f"| `{m}` | {_fmt(r['passa'])} | {_fmt(r['esquema_valido'])} | {len(r['prescricoes'])} em {r['seguranca_execucoes']}"
            f" ({r['seguranca_julgadas']} julgadas) | {_fmt(r['fidelidade'])} / {_fmt(r['fidelidade_semente_1'])} (n={r['fidelidade_julgadas']}) | {_fmt(r['cobertura_termos'])}"
            f" | {_fmt(r['rouge_l_precisao'])} | {_fmt(r['bertscore_precisao'])} | {_fmt(r['latencia_p50'], False)} | {_fmt(r['latencia_p95'], False)}"
            f" | {_fmt(r['tokens_por_segundo'], False)} | {vram_txt} | {_fmt(fer.get('escolha_correta'))} / {_fmt(fer.get('argumentos_corretos'))} |")
    linhas += ["", f"## Diferença para a referência (`{rel['referencia']}`), bootstrap pareado", "",
               "| Modelo | Fidelidade: dif. [IC 95%] | Cobertura: dif. [IC 95%] |", "|---|---|---|"]
    for m, c in rel["comparacao_com_referencia"].items():
        celulas = []
        for campo in ("fidelidade", "cobertura_termos"):
            b = c[campo]
            celulas.append("n/d" if not b else
                           f"{b['diferenca'] * 100:+.1f} p.p. [{b['ic95'][0] * 100:+.1f}; {b['ic95'][1] * 100:+.1f}]"
                           + (" *" if b["significativa"] else " (empate)"))
        linhas.append(f"| `{m}` | {celulas[0]} | {celulas[1]} |")
    linhas += ["", "`*` = intervalo sem o zero. Sem asterisco, a diferença é empate técnico.", "",
               "## Classificação", "",
               f"Ordem: {', '.join(f'`{m}`' for m in rel['classificacao']) or 'n/d'}. "
               f"Empatados com o líder (desempate por latência e VRAM): {', '.join(f'`{m}`' for m in rel['empatados_com_o_lider']) or 'n/d'}.",
               "", f"Finalistas (principal e reserva): {', '.join(f'`{m}`' for m in rel['finalistas']) or 'n/d'}."]
    if rel.get("entre_finalistas"):
        for campo, b in rel["entre_finalistas"].items():
            if b:
                linhas.append(f"- {campo}, 1º menos 2º: {b['diferenca'] * 100:+.1f} p.p. "
                              f"[{b['ic95'][0] * 100:+.1f}; {b['ic95'][1] * 100:+.1f}]"
                              + (" *" if b["significativa"] else " (empate)"))
    linhas.append("")
    return "\n".join(linhas)


def gravar(modelos: List[str]) -> Dict[str, Any]:
    rel = montar(modelos)
    config.RESULTADOS_JSON_PATH.write_text(json.dumps(rel, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    config.RESULTADOS_MD_PATH.write_text(markdown(rel), encoding="utf-8")
    return rel
