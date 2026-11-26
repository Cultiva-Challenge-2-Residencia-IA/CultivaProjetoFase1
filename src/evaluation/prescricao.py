"""Medição do guardrail de prescrição (issue #39). Critérios: eval/prescricao/criterios.md.

    uv run python -m src.evaluation.prescricao --split dev|test [--sem-llm]

Grava `eval/prescricao/resultado_<split>.json` com recall e especificidade, só regras e com a
camada LLM local (exige o Ollama, salvo com --sem-llm).
"""

import argparse
import json
import sys

from src.agent.guardrails import LegalGuardrail
from src.agent.llm_json import ClienteJsonOllama
from src.config import PRESCRICAO_LLM_TIMEOUT, PROJECT_ROOT

PASTA = PROJECT_ROOT / "eval" / "prescricao"


def medir(casos, guardrail: LegalGuardrail) -> dict:
    erros, vp, fn, vn, fp = [], 0, 0, 0, 0
    for caso in casos:
        restrito = guardrail.assess_and_reframe(
            caso["mensagem"], condicao_de_saude=caso.get("condicao_de_saude", False)).is_restricted_by_law_8234
        if caso["restrito"]:
            vp, fn = vp + int(restrito), fn + int(not restrito)
        else:
            vn, fp = vn + int(not restrito), fp + int(restrito)
        if restrito != caso["restrito"]:
            erros.append({"id": caso["id"], "mensagem": caso["mensagem"], "esperado": caso["restrito"]})
    return {"recall": round(vp / (vp + fn), 3) if vp + fn else None,
            "especificidade": round(vn / (vn + fp), 3) if vn + fp else None,
            "restritos": vp + fn, "que_passam": vn + fp, "erros": erros}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--split", choices=["dev", "test"], default="dev")
    parser.add_argument("--sem-llm", action="store_true", help="Mede só as regras")
    args = parser.parse_args()
    casos = json.loads((PASTA / f"{args.split}.json").read_text(encoding="utf-8"))["casos"]
    resultado = {"split": args.split, "so_regras": medir(casos, LegalGuardrail())}
    if not args.sem_llm:
        llm = ClienteJsonOllama("guardrail_prescricao", timeout=max(PRESCRICAO_LLM_TIMEOUT, 30.0), num_predict=64)
        if not llm.disponivel():
            print("Ollama indisponível: use --sem-llm para medir só as regras.", file=sys.stderr)
            return 1
        guardrail = LegalGuardrail()
        guardrail.classificador_llm = llm
        resultado["regras_e_llm"] = medir(casos, guardrail)
    destino = PASTA / f"resultado_{args.split}.json"
    destino.write_text(json.dumps(resultado, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for nome in ("so_regras", "regras_e_llm"):
        if nome in resultado:
            r = resultado[nome]
            print(f"{nome}: recall {r['recall']} ({r['restritos']}), especificidade {r['especificidade']} "
                  f"({r['que_passam']}), erros {[e['id'] for e in r['erros']]}")
    print(f"Gravado em {destino.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
