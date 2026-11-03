"""Uso: python -m chat [--provedor ollama|falso]"""

import argparse
import sys

import httpx

from chat.sessao import SessaoChat
from config import ConfiguracaoInvalida, carregar_configuracao
from modelo import ModeloOllama, criar_modelo
from orquestracao import Cultiva


def _verificar_ollama(modelo: ModeloOllama) -> str | None:
    """Mensagem de erro se o Ollama não estiver pronto, ou None."""
    try:
        disponiveis = modelo.modelos_disponiveis()
    except httpx.HTTPError:
        return (
            f"Não consegui falar com o Ollama em {modelo.url}.\n"
            "Abra o app do Ollama (ou rode 'ollama serve') e confira CULTIVA_OLLAMA_URL no .env."
        )
    nomes = {nome.removesuffix(":latest") for nome in disponiveis} | set(disponiveis)
    if modelo.nome not in nomes:
        return (
            f"O modelo {modelo.nome!r} não está baixado no Ollama.\n"
            f"Baixe com 'ollama pull {modelo.nome}' ou ajuste CULTIVA_MODELO no .env.\n"
            f"Disponíveis: {', '.join(disponiveis) or 'nenhum'}"
        )
    return None


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m chat")
    p.add_argument("--provedor", default=None, help="ollama ou falso (vence o .env)")
    args = p.parse_args(argv)

    try:
        config = carregar_configuracao(provedor=args.provedor)
    except ConfiguracaoInvalida as erro:
        print(erro, file=sys.stderr)
        return 1

    modelo = criar_modelo(config)
    if isinstance(modelo, ModeloOllama):
        erro = _verificar_ollama(modelo)
        if erro:
            print(erro, file=sys.stderr)
            return 1

    sessao = SessaoChat(Cultiva(modelo))
    print("CULTIVA, Aba Nutrição")
    for chave, valor in config.valores.items():
        print(f"  {chave}={valor} ({config.origem[chave]})")
    print("Perfil e Registros de exemplo, em memória. Digite /ajuda para ver os comandos.\n")
    while True:
        try:
            linha = input("você> ")
        except (EOFError, KeyboardInterrupt):
            print()
            break
        saida = sessao.processar(linha)
        if saida is None:
            break
        if saida:
            print(f"\ncultiva> {saida}\n")
    print("Até mais.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
