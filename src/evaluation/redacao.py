"""Medição da redação final e do esclarecimento (issue #104). Critérios: eval/redacao/criterios.md.

    uv run python -m src.evaluation.redacao responder --split dev
    uv run python -m src.evaluation.redacao resultado --split dev

`responder` roda cada pergunta no serviço de chat real com e sem redação e grava:
- `resultado_<split>.json`: as duas respostas, a aceitação, o tempo e o esclarecimento;
- `cego_<split>.json`: os pares para o juiz, em ordem sorteada (A/B), sem dizer qual é a redigida;
- `chave_<split>.json`: qual letra é a redigida (o juiz não lê este arquivo).
`resultado` lê `julgamento_<split>.json` (do juiz) e calcula utilidade e exagero. Exige o Ollama.
"""

import argparse
import json
from pathlib import Path
import random
import statistics
import sys
import tempfile
import time

from src.chat.historico import HistoricoSQLite
from src.config import PROJECT_ROOT

PASTA = PROJECT_ROOT / "eval" / "redacao"


def _gravar(nome: str, dados) -> None:
    (PASTA / nome).write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def responder(split: str) -> int:
    from src.chat.fabrica import criar_servico

    casos = json.loads((PASTA / "casos.json").read_text(encoding="utf-8"))[split]
    with tempfile.TemporaryDirectory() as pasta:
        servico = criar_servico(enable_ollama=True, historico=HistoricoSQLite(Path(pasta) / "h.sqlite3"))
        if servico.llm is None:
            print("Ollama indisponível.", file=sys.stderr)
            return 1
        servico.executar_em_segundo_plano = lambda tarefa: None
        registros = []
        for caso in casos:
            registro = {"id": caso["id"], "mensagem": caso["mensagem"], "vago": caso["vago"]}
            for modo, ligada in (("sem", False), ("com", True)):
                servico.redacao = ligada
                inicio = time.perf_counter()
                r = servico.enviar(caso["chat"], "u", f"{caso['id']}-{modo}", caso["mensagem"])
                registro[modo] = {"tipo": r.tipo, "texto": r.texto, "texto_com_marcadores": r.texto_com_marcadores,
                                  "redacao": r.redacao, "segundos": round(time.perf_counter() - inicio, 1),
                                  "status": [resp.fundamentacao_status for resp in r.respostas.values()]}
                print(caso["id"], modo, r.tipo, r.redacao, registro[modo]["segundos"], file=sys.stderr)
            registros.append(registro)
    sorteio = random.Random(f"redacao-{split}")
    cegos, chave = [], {}
    for reg in registros:
        if reg["com"]["redacao"] != "aceita":
            continue  # sem redação aceita, as duas versões são iguais
        redigida_e_a = sorteio.random() < 0.5
        a, b = (reg["com"], reg["sem"]) if redigida_e_a else (reg["sem"], reg["com"])
        cegos.append({"id": reg["id"], "pergunta": reg["mensagem"], "A": a["texto"], "B": b["texto"],
                      "frases_de_origem": reg["sem"]["texto_com_marcadores"],
                      "versao_reescrita": reg["com"]["texto_com_marcadores"]})
        chave[reg["id"]] = "A" if redigida_e_a else "B"
    _gravar(f"resultado_{split}.json", registros)
    _gravar(f"cego_{split}.json", cegos)
    _gravar(f"chave_{split}.json", chave)
    print(f"{len(registros)} perguntas; {len(cegos)} pares para o juiz em eval/redacao/cego_{split}.json")
    return 0


def resultado(split: str) -> int:
    registros = json.loads((PASTA / f"resultado_{split}.json").read_text(encoding="utf-8"))
    chave = json.loads((PASTA / f"chave_{split}.json").read_text(encoding="utf-8"))
    julgamento = json.loads((PASTA / f"julgamento_{split}.json").read_text(encoding="utf-8"))
    llm = [r for r in registros if r["com"]["redacao"] in ("aceita", "recusada")]
    vence = perde = empate = alem = frases = 0
    for caso_id, j in julgamento.items():
        if j["melhor"] == "empate":
            empate += 1
        elif j["melhor"] == chave[caso_id]:
            vence += 1
        else:
            perde += 1
        alem += j["frases_alem_da_origem"]
        frases += j["frases_reescritas"]
    vagos = [r for r in registros if r["vago"]]
    nao_vagos = [r for r in registros if not r["vago"]]
    resumo = {
        "aceitacao": round(sum(r["com"]["redacao"] == "aceita" for r in llm) / len(llm), 3) if llm else None,
        "respostas_llm": len(llm),
        "utilidade_vitorias_da_redigida": round(vence / (vence + perde), 3) if vence + perde else None,
        "pares": {"vence": vence, "perde": perde, "empate": empate},
        "exagero": round(alem / frases, 3) if frases else None,
        "mediana_s_sem": statistics.median(r["sem"]["segundos"] for r in registros),
        "mediana_s_com": statistics.median(r["com"]["segundos"] for r in registros),
        "esclarecimento_nos_vagos": round(sum(r["com"]["tipo"] == "esclarecimento" for r in vagos) / len(vagos), 3)
        if vagos else None,
        "esclarecimento_nos_demais": round(sum(r["com"]["tipo"] == "esclarecimento" for r in nao_vagos)
                                           / len(nao_vagos), 3) if nao_vagos else None,
    }
    _gravar(f"resumo_{split}.json", resumo)
    print(json.dumps(resumo, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("comando", choices=["responder", "resultado"])
    parser.add_argument("--split", choices=["dev", "test"], default="dev")
    args = parser.parse_args()
    return responder(args.split) if args.comando == "responder" else resultado(args.split)


if __name__ == "__main__":
    raise SystemExit(main())
