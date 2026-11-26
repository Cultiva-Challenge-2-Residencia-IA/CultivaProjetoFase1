"""Régua de perguntas reais: o chat inteiro medido contra o que seria uma boa resposta (issue #118).

Critérios em eval/regua/criterios.md, escritos antes de medir. Exige o Ollama.

    uv run python -m src.evaluation.regua responder --split dev --rotulo base
    uv run python -m src.evaluation.regua exportar --split dev --rotulo base
    uv run python -m src.evaluation.regua resultado --split dev --rotulo base

`responder` roda cada caso no serviço de chat real (com as mensagens anteriores do caso, quando há) e
grava `respostas_<split>_<rotulo>.json`. `exportar` grava `cego_<split>_<rotulo>.json` para os juízes:
a pergunta, o que seria uma boa resposta, a cobertura do corpus, o texto exibido e os Trechos citados,
sem a configuração medida. Dois juízes gravam `julgamento_<split>_<rotulo>_j1.json` e `_j2.json`;
`resultado` aponta as divergências e, com `_j3.json` (desempate), calcula as medidas.
"""

import argparse
import json
from pathlib import Path
import sys
import tempfile
import time
from typing import Any, Dict, List

from src.chat.historico import HistoricoSQLite
from src.config import PROJECT_ROOT

PASTA = PROJECT_ROOT / "eval" / "regua"
CRITERIOS = ("responde", "fiel", "tom", "nao_prescreve")


def _ler(nome: str) -> Any:
    return json.loads((PASTA / nome).read_text(encoding="utf-8"))


def _gravar(nome: str, dados: Any) -> None:
    (PASTA / nome).write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _trechos_citados(resposta) -> List[Dict[str, str]]:
    saida = []
    for r in resposta.respostas.values():
        por_id = {item.chunk.chunk_id: item.chunk for item in r.retrieved_chunks}
        for chunk_id in r.trechos_citados:
            chunk = por_id.get(chunk_id)
            if chunk is not None:
                saida.append({"fonte": chunk.title, "texto": chunk.raw_text})
    return saida


def responder(split: str, rotulo: str) -> int:
    from src.chat.fabrica import criar_servico

    casos = _ler("casos.json")[split]
    registros = []
    with tempfile.TemporaryDirectory() as pasta:
        servico = criar_servico(enable_ollama=True, historico=HistoricoSQLite(Path(pasta) / "h.sqlite3"))
        if servico.llm is None:
            print("Ollama indisponível.", file=sys.stderr)
            return 1
        servico.executar_em_segundo_plano = lambda tarefa: None  # sem Fatos do Usuário na régua
        inicio_total = time.perf_counter()
        for n, caso in enumerate(casos, 1):
            conversa = f"{rotulo}-{caso['id']}"
            for anterior in caso.get("historico", []):
                servico.enviar(caso["chat"], "regua", conversa, anterior)
            inicio = time.perf_counter()
            r = servico.enviar(caso["chat"], "regua", conversa, caso["pergunta"])
            segundos = round(time.perf_counter() - inicio, 1)
            registros.append({
                "id": caso["id"], "tipo": r.tipo, "areas": r.areas, "texto": r.texto,
                "texto_com_marcadores": r.texto_com_marcadores, "redacao": r.redacao, "segundos": segundos,
                "status": {a: x.fundamentacao_status for a, x in r.respostas.items()},
                "abstencao": any(x.abstencao for x in r.respostas.values()),
                "pedido_individual": any(x.guardrail_triggered for x in r.respostas.values()),
                "consulta_da_busca": {a: x.effective_query for a, x in r.respostas.items()},
                "trechos_citados": _trechos_citados(r),
            })
            decorrido = time.perf_counter() - inicio_total
            print(f"[{n}/{len(casos)}] {caso['id']} {r.tipo} {segundos}s; faltam cerca de "
                  f"{decorrido / n * (len(casos) - n) / 60:.0f} min", file=sys.stderr, flush=True)
    _gravar(f"respostas_{split}_{rotulo}.json", registros)
    return 0


def exportar(split: str, rotulo: str) -> int:
    casos = {c["id"]: c for c in _ler("casos.json")[split]}
    cegos = []
    for reg in _ler(f"respostas_{split}_{rotulo}.json"):
        caso = casos[reg["id"]]
        cegos.append({"id": reg["id"], "tipo_da_pergunta": caso["tipo"], "mensagens_anteriores": caso.get("historico", []),
                      "pergunta": caso["pergunta"], "boa_resposta": caso["boa_resposta"],
                      "corpus_cobre_o_tema": caso["cobertura"], "resposta": reg["texto"],
                      "trechos_citados": reg["trechos_citados"]})
    _gravar(f"cego_{split}_{rotulo}.json", cegos)
    print(f"{len(cegos)} respostas em eval/regua/cego_{split}_{rotulo}.json")
    return 0


def _julgamentos(split: str, rotulo: str) -> Dict[str, Dict[str, Any]]:
    j1 = _ler(f"julgamento_{split}_{rotulo}_j1.json")
    j2 = _ler(f"julgamento_{split}_{rotulo}_j2.json")
    caminho_j3 = PASTA / f"julgamento_{split}_{rotulo}_j3.json"
    j3 = json.loads(caminho_j3.read_text(encoding="utf-8")) if caminho_j3.exists() else {}
    final, divergentes = {}, []
    for caso_id, a in j1.items():
        b = j2[caso_id]
        final[caso_id] = {}
        for criterio in CRITERIOS:
            if a[criterio] == b[criterio]:
                final[caso_id][criterio] = a[criterio]
            elif caso_id in j3:
                final[caso_id][criterio] = j3[caso_id][criterio]
            else:
                divergentes.append(caso_id)
                final[caso_id][criterio] = None
    return final, sorted(set(divergentes)), j1, j2


def resultado(split: str, rotulo: str) -> int:
    casos = {c["id"]: c for c in _ler("casos.json")[split]}
    respostas = {r["id"]: r for r in _ler(f"respostas_{split}_{rotulo}.json")}
    final, divergentes, j1, j2 = _julgamentos(split, rotulo)
    if any(v is None for j in final.values() for v in j.values()):
        print(f"Divergências sem desempate (grave _j3.json): {divergentes}", file=sys.stderr)
        _gravar(f"divergencias_{split}_{rotulo}.json", divergentes)
        return 2

    def taxa(ids, criterio):
        ids = list(ids)
        return round(sum(final[i][criterio] for i in ids) / len(ids), 3) if ids else None

    todos = list(final)
    nao_cobertos = [i for i in todos if casos[i]["cobertura"] == "nao_coberto"]
    cobertos = [i for i in todos if casos[i]["cobertura"] == "coberto"]
    concordancia = sum(j1[i][c] == j2[i][c] for i in todos for c in CRITERIOS) / (len(todos) * len(CRITERIOS))
    resumo = {
        "rotulo": rotulo, "casos": len(todos),
        "responde": taxa(todos, "responde"),
        "fiel": taxa(todos, "fiel"),
        "tom": taxa(todos, "tom"),
        "nao_prescreve": taxa(todos, "nao_prescreve"),
        "responde_por_tipo": {t: taxa([i for i in todos if casos[i]["tipo"] == t], "responde")
                              for t in sorted({casos[i]["tipo"] for i in todos})},
        "nao_sei_nos_nao_cobertos": round(sum(respostas[i]["abstencao"] for i in nao_cobertos) / len(nao_cobertos), 3)
        if nao_cobertos else None,
        "nao_sei_indevido_nos_cobertos": round(sum(respostas[i]["abstencao"] for i in cobertos) / len(cobertos), 3)
        if cobertos else None,
        "concordancia_entre_juizes": round(concordancia, 3),
        "desempates": len(divergentes),
        "mediana_s": sorted(r["segundos"] for r in respostas.values())[len(respostas) // 2],
    }
    _gravar(f"resumo_{split}_{rotulo}.json", resumo)
    print(json.dumps(resumo, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("comando", choices=["responder", "exportar", "resultado"])
    parser.add_argument("--split", choices=["dev", "test"], default="dev")
    parser.add_argument("--rotulo", required=True, help="nome da configuração medida (ex.: base, issue120)")
    args = parser.parse_args()
    return {"responder": responder, "exportar": exportar, "resultado": resultado}[args.comando](args.split, args.rotulo)


if __name__ == "__main__":
    raise SystemExit(main())
