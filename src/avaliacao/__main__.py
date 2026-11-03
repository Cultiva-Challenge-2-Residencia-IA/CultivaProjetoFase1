"""Uso: python -m avaliacao [--provedor ollama|falso] [--conjunto PASTA] [--saida PASTA]

Sai com código 1 se algum caso crítico (risco, fora de escopo, adversarial) falhar.
"""

import argparse
import sys
from pathlib import Path

from avaliacao.harness import TIPOS_CRITICOS, executar, salvar
from modelo import criar_modelo
from rag.chunking import RAIZ


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m avaliacao")
    p.add_argument("--provedor", default=None, help="ollama (padrão) ou falso")
    p.add_argument("--conjunto", type=Path, default=RAIZ / "eval" / "golden" / "dev")
    p.add_argument("--saida", type=Path, default=RAIZ / "eval" / "runs")
    args = p.parse_args(argv)

    relatorio = executar(criar_modelo(args.provedor), args.conjunto)
    caminho = salvar(relatorio, args.saida)

    print(
        f"modelo={relatorio.modelo} prompt={relatorio.prompt_versao} corpus=v{relatorio.corpus_versao}"
    )
    for tipo, r in sorted(relatorio.por_tipo().items()):
        marca = " (crítico)" if tipo in TIPOS_CRITICOS else ""
        print(f"  {tipo:<18} {r['ok']}/{r['total']}{marca}")
    for c in relatorio.casos:
        if not c.ok:
            print(f"  FALHOU {c.id}: {', '.join(c.falhas)}")
    print(f"relatório: {caminho}")
    print("APROVADO" if relatorio.aprovado else "REPROVADO (caso crítico falhou)")
    return 0 if relatorio.aprovado else 1


if __name__ == "__main__":
    sys.exit(main())
