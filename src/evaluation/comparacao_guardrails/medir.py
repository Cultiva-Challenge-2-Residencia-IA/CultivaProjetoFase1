"""Medição e relatório da issue #52 (critérios em eval/comparacao_guardrails/criterios.md)."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.evaluation.comparacao_guardrails import candidatos, casos, config, respostas


def _arquivo(tarefa: str, candidato: str) -> Path:
    return config.BRUTOS_DIR / tarefa / f"{candidato}.jsonl"


def _ler(caminho: Path) -> List[Dict[str, Any]]:
    if not caminho.exists():
        return []
    return [json.loads(x) for x in caminho.read_text(encoding="utf-8").splitlines() if x.strip()]


def _gravar_vereditos(tarefa: str, nome: str, itens: List[Dict[str, Any]], julgar) -> None:
    destino = _arquivo(tarefa, nome)
    destino.parent.mkdir(parents=True, exist_ok=True)
    feitos = {x["id"] for x in _ler(destino) if x.get("erro") is None}
    with destino.open("a", encoding="utf-8") as saida:
        for item in itens:
            if item["id"] in feitos:
                continue
            v = julgar(item)
            linha = {"id": item["id"], "sustentada": v.sustentada, "segundos": round(v.segundos, 3),
                     "chamadas": v.chamadas, "erro": v.erro, "detalhe": v.detalhe, "maquina": config.MAQUINA or None}
            saida.write(json.dumps(linha, ensure_ascii=False) + "\n")
            saida.flush()
            print(f"{tarefa} {nome:14s} {item['id']:28s} {v.sustentada} {v.segundos:6.1f} s {v.erro or ''}", flush=True)


def fundamentacao(nomes: List[str]) -> None:
    itens = casos.carregar()
    for nome in nomes:
        if nome == "direto_pre":
            continue  # não julga resposta: decide antes da geração
        c = candidatos.criar(nome)
        _gravar_vereditos("fundamentacao", nome, itens, lambda i: c.verificar(i["pergunta"], i["trechos"], i["resposta"]))


def fundamentacao_reais(nomes: List[str]) -> None:
    itens = casos.carregar_reais()
    if not itens:
        raise SystemExit("Amostra da #12 não encontrada (eval/fundamentacao/amostra_para_avaliar.csv).")
    for nome in nomes:
        if nome == "direto_pre":
            continue
        c = candidatos.criar(nome)
        _gravar_vereditos("fundamentacao_reais", nome, itens,
                          lambda i: c.verificar(i["pergunta"], i["trechos"], i["resposta"]))


def abstencao(nomes: List[str]) -> None:
    # As camadas locais são o piso: o que elas já recusaram não vai ao candidato.
    itens = [r for r in respostas.ler() if not r["nao_sei_local"] and not r["risco"]]
    for nome in nomes:
        c = candidatos.criar(nome)
        _gravar_vereditos("abstencao", nome, itens, lambda i: c.verificar(i["pergunta"], i["trechos"], i["resposta"]))


def _taxa(valores: List[bool]) -> Optional[Dict[str, Any]]:
    if not valores:
        return None
    n, k = len(valores), sum(valores)
    return {"k": k, "n": n, "taxa": round(k / n, 4), "ic95": wilson(k, n)}


def wilson(k: int, n: int, z: float = 1.96) -> List[float]:
    if n == 0:
        return [0.0, 0.0]
    p = k / n
    centro = (p + z * z / (2 * n)) / (1 + z * z / n)
    margem = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return [round(max(0.0, centro - margem), 4), round(min(1.0, centro + margem), 4)]


def _percentil(valores: List[float], q: float) -> Optional[float]:
    if not valores:
        return None
    v = sorted(valores)
    return round(v[min(len(v) - 1, int(round(q * (len(v) - 1))))], 2)


def resumo_fundamentacao(nome: str) -> Optional[Dict[str, Any]]:
    vereditos = {x["id"]: x for x in _ler(_arquivo("fundamentacao", nome))}
    if not vereditos:
        return None
    itens = [i for i in casos.carregar() if i["id"] in vereditos]
    por_tipo = {}
    for tipo in ("fiel", "inventada", "trocada"):
        grupo = [vereditos[i["id"]] for i in itens if i["tipo"] == tipo]
        # Acerto: fiel aceita; inventada e trocada barradas. Erro do candidato conta como erro.
        acertos = [(v["sustentada"] is True) if tipo == "fiel" else (v["sustentada"] is False) for v in grupo]
        por_tipo[tipo] = _taxa(acertos)
    tempos = [v["segundos"] for v in vereditos.values() if v.get("erro") is None]
    return {"por_tipo": por_tipo, "erros": sum(v.get("erro") is not None for v in vereditos.values()),
            "segundos_p50": _percentil(tempos, 0.5), "segundos_p95": _percentil(tempos, 0.95)}


def resumo_reais(nome: str) -> Optional[Dict[str, Any]]:
    """Concordância com os rótulos do juiz automático do #68 (informativo)."""
    vereditos = {x["id"]: x for x in _ler(_arquivo("fundamentacao_reais", nome))}
    itens = [i for i in casos.carregar_reais() if i["id"] in vereditos]
    if not itens:
        return None
    pares = [(i["sustentada"], vereditos[i["id"]]["sustentada"]) for i in itens]
    validos = [(a, b) for a, b in pares if b is not None]
    return {
        "concordancia": _taxa([a == b for a, b in validos]),
        "sustentada_aceita": _taxa([b for a, b in validos if a]),
        "nao_sustentada_barrada": _taxa([not b for a, b in validos if not a]),
        "kappa": kappa([a for a, _ in validos], [b for _, b in validos]),
        "erros": len(pares) - len(validos),
    }


def kappa(a: List[bool], b: List[bool]) -> Optional[float]:
    n = len(a)
    if n == 0:
        return None
    observada = sum(x == y for x, y in zip(a, b)) / n
    pa, pb = sum(a) / n, sum(b) / n
    esperada = pa * pb + (1 - pa) * (1 - pb)
    return None if esperada == 1 else round((observada - esperada) / (1 - esperada), 4)


def resumo_abstencao(nome: str) -> Optional[Dict[str, Any]]:
    vereditos = {x["id"]: x for x in _ler(_arquivo("abstencao", nome))}
    if not vereditos:
        return None
    linhas = []
    for r in respostas.ler():
        if r["nao_sei_local"] or r["risco"]:
            nao_sei = True  # piso local: o candidato não pode desfazer
        elif r["id"] in vereditos:
            nao_sei = vereditos[r["id"]]["sustentada"] is False
        else:
            continue
        linhas.append({**r, "nao_sei": nao_sei})

    def grupo(filtro) -> Optional[Dict[str, Any]]:
        return _taxa([x["nao_sei"] for x in linhas if filtro(x)])

    tempos = [v["segundos"] for v in vereditos.values() if v.get("erro") is None]
    chamadas = [v["chamadas"] for v in vereditos.values()]
    return {
        "nutricao_fora_do_corpus": {
            "test": grupo(lambda x: x["tipo"] == "nutricao_fora_do_corpus" and x["split"] == "test"),
            "todos": grupo(lambda x: x["tipo"] == "nutricao_fora_do_corpus"),
        },
        "fora_de_nutricao": grupo(lambda x: x["tipo"] == "fora_de_nutricao"),
        "recusa_indevida": {
            "abstencao_test": grupo(lambda x: x["conjunto"] == "abstencao" and x["esperado"] == "responder"
                                    and x["split"] == "test"),
            "abstencao_todos": grupo(lambda x: x["conjunto"] == "abstencao" and x["esperado"] == "responder"),
            "golden_v2": grupo(lambda x: x["conjunto"] == "golden_v2"),
        },
        "erros": sum(v.get("erro") is not None for v in vereditos.values()),
        "segundos_p50": _percentil(tempos, 0.5),
        "segundos_p95": _percentil(tempos, 0.95),
        "chamadas_por_pergunta": round(sum(chamadas) / len(chamadas), 2) if chamadas else None,
    }


def linha_de_base() -> Dict[str, Any]:
    """Só as camadas locais (cosseno e vocabulário da #6), sem candidato."""
    linhas = respostas.ler()

    def grupo(filtro) -> Optional[Dict[str, Any]]:
        return _taxa([x["nao_sei_local"] or x["risco"] for x in linhas if filtro(x)])

    return {
        "nutricao_fora_do_corpus": {
            "test": grupo(lambda x: x["tipo"] == "nutricao_fora_do_corpus" and x["split"] == "test"),
            "todos": grupo(lambda x: x["tipo"] == "nutricao_fora_do_corpus"),
        },
        "fora_de_nutricao": grupo(lambda x: x["tipo"] == "fora_de_nutricao"),
        "recusa_indevida": {
            "abstencao_test": grupo(lambda x: x["conjunto"] == "abstencao" and x["esperado"] == "responder"
                                    and x["split"] == "test"),
            "abstencao_todos": grupo(lambda x: x["conjunto"] == "abstencao" and x["esperado"] == "responder"),
            "golden_v2": grupo(lambda x: x["conjunto"] == "golden_v2"),
        },
        "segundos_geracao_p50": _percentil([x["segundos_geracao"] for x in linhas], 0.5),
    }


def relatorio(nomes: List[str]) -> Dict[str, Any]:
    rel = {
        "modelo": config.MODELO,
        "maquina": config.MAQUINA or "referência",
        "criterios": "eval/comparacao_guardrails/criterios.md",
        "camadas_locais": linha_de_base(),
        "candidatos": {n: {"abstencao": resumo_abstencao(n), "fundamentacao": resumo_fundamentacao(n),
                            "fundamentacao_reais": resumo_reais(n)} for n in nomes},
    }
    config.EVAL_DIR.mkdir(parents=True, exist_ok=True)
    config.RESULTADOS_JSON_PATH.write_text(json.dumps(rel, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    config.RESULTADOS_MD_PATH.write_text(markdown(rel), encoding="utf-8")
    return rel


def _fmt(t: Optional[Dict[str, Any]]) -> str:
    if not t:
        return "n/d"
    return f"{t['k']}/{t['n']} ({t['taxa']:.0%}) [{t['ic95'][0]:.0%}; {t['ic95'][1]:.0%}]"


def markdown(rel: Dict[str, Any]) -> str:
    lin = [
        "# Comparação de frameworks de guardrail (issue #52): resultados",
        "",
        "Gerado por `uv run python -m src.evaluation.comparacao_guardrails relatorio`. Não edite à mão.",
        "",
        f"Modelo: `{rel['modelo']}` · máquina: {rel['maquina']} · critérios: [`criterios.md`](criterios.md).",
        "Entre colchetes, o intervalo de Wilson de 95%.",
        "",
        "## \"Não sei\"",
        "",
        "| Camada | Nutrição fora do corpus (test) | Nutrição fora do corpus (todos) | Fora de Nutrição | "
        "Recusa indevida (golden v2) | Recusa indevida (abstenção, todos) | Tempo p50 / p95 (s) | Chamadas |",
        "|---|---|---|---|---|---|---|---:|",
    ]
    base = rel["camadas_locais"]
    lin.append(f"| Só camadas locais | {_fmt(base['nutricao_fora_do_corpus']['test'])} | "
               f"{_fmt(base['nutricao_fora_do_corpus']['todos'])} | {_fmt(base['fora_de_nutricao'])} | "
               f"{_fmt(base['recusa_indevida']['golden_v2'])} | {_fmt(base['recusa_indevida']['abstencao_todos'])} | "
               "0 | 0 |")
    for nome, r in rel["candidatos"].items():
        a = r["abstencao"]
        if not a:
            continue
        lin.append(f"| `{nome}` | {_fmt(a['nutricao_fora_do_corpus']['test'])} | "
                   f"{_fmt(a['nutricao_fora_do_corpus']['todos'])} | {_fmt(a['fora_de_nutricao'])} | "
                   f"{_fmt(a['recusa_indevida']['golden_v2'])} | {_fmt(a['recusa_indevida']['abstencao_todos'])} | "
                   f"{a['segundos_p50']} / {a['segundos_p95']} | {a['chamadas_por_pergunta']} |")
    lin += ["", "## Fundamentação", "",
            "| Candidato | Fiel aceita | Inventada barrada | Trocada barrada | Erros | Tempo p50 / p95 (s) |",
            "|---|---|---|---|---:|---|"]
    for nome, r in rel["candidatos"].items():
        f = r["fundamentacao"]
        if not f:
            continue
        t = f["por_tipo"]
        lin.append(f"| `{nome}` | {_fmt(t['fiel'])} | {_fmt(t['inventada'])} | {_fmt(t['trocada'])} | "
                   f"{f['erros']} | {f['segundos_p50']} / {f['segundos_p95']} |")
    lin += ["", "## Apoio: frases reais da amostra da #12 (rótulos do juiz automático do #68)", "",
            "| Candidato | Concordância | Sustentada aceita | Não sustentada barrada | Kappa |",
            "|---|---|---|---|---:|"]
    for nome, r in rel["candidatos"].items():
        f = r.get("fundamentacao_reais")
        if not f:
            continue
        lin.append(f"| `{nome}` | {_fmt(f['concordancia'])} | {_fmt(f['sustentada_aceita'])} | "
                   f"{_fmt(f['nao_sustentada_barrada'])} | {f['kappa']} |")
    return "\n".join(lin) + "\n"
