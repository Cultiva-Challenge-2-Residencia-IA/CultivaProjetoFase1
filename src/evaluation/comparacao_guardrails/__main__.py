"""Linha de comando da comparação de frameworks de guardrail (issue #52).

    uv sync --group guardrails-frameworks
    uv run python -m src.evaluation.comparacao_guardrails casos           # casos de fundamentação
    uv run python -m src.evaluation.comparacao_guardrails respostas       # respostas do sistema atual
    uv run python -m src.evaluation.comparacao_guardrails fundamentacao [--candidatos ...]
    uv run python -m src.evaluation.comparacao_guardrails fundamentacao-reais [--candidatos ...]   # apoio, #68
    uv run python -m src.evaluation.comparacao_guardrails abstencao [--candidatos ...]
    uv run python -m src.evaluation.comparacao_guardrails relatorio
"""

from __future__ import annotations

import argparse
import sys
from typing import List

from src.evaluation.comparacao_guardrails import casos, config, medir, respostas


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Comparação de frameworks de guardrail (issue #52).")
    sub = parser.add_subparsers(dest="comando", required=True)
    sub.add_parser("casos")
    sub.add_parser("respostas")
    for nome in ("fundamentacao", "fundamentacao-reais", "abstencao", "relatorio"):
        p = sub.add_parser(nome)
        p.add_argument("--candidatos", nargs="+", choices=config.CANDIDATOS, default=config.CANDIDATOS)
    args = parser.parse_args(argv)

    if args.comando == "casos":
        dados = casos.montar()
        print(f"{len(dados['itens'])} casos de fundamentação em {config.CASOS_FUNDAMENTACAO_PATH}")
    elif args.comando == "respostas":
        respostas.gerar()
    elif args.comando == "fundamentacao":
        medir.fundamentacao(args.candidatos)
    elif args.comando == "fundamentacao-reais":
        medir.fundamentacao_reais(args.candidatos)
    elif args.comando == "abstencao":
        medir.abstencao(args.candidatos)
    else:
        medir.relatorio(args.candidatos)
        print(config.RESULTADOS_MD_PATH.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
