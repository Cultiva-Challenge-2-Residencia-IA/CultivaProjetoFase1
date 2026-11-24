"""Demonstração do sistema multiagentes (issue #99), reproduzível por um comando:

    uv run python -m src.demo_multiagentes [--sem-llm]

Mostra o Chat geral roteando para um agente ou para os dois, o Sincronizador, a pergunta de
continuação, um Chat de área indicando o chat certo e os portões. Usa um Histórico temporário.
"""

import argparse
from pathlib import Path
import tempfile

from src.chat.fabrica import criar_servico
from src.chat.historico import HistoricoSQLite

ROTEIRO = [
    ("geral", "Quantos minutos de atividade física por semana a OMS recomenda para adultos?"),
    ("geral", "E para idosos?"),
    ("geral", "O que comer antes do treino e quantas vezes por semana devo fazer musculação?"),
    ("nutricao", "Quais alimentos são fontes de fibra?"),
    ("nutricao", "Quantas séries de agachamento são recomendadas para iniciantes?"),
    ("saude_fisica", "Monte um treino de musculação para mim"),
    ("geral", "Senti dor no peito forte enquanto corria"),
    ("geral", "Como organizar meus estudos para a prova?"),
]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--sem-llm", action="store_true", help="Sem Ollama: regras e síntese extrativa")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as pasta:
        servico = criar_servico(enable_ollama=not args.sem_llm,
                                historico=HistoricoSQLite(Path(pasta) / "demo.sqlite3"))
        print(f"Reescrita e Sincronizador com LLM: {'sim' if servico.llm else 'não'}\n")
        for chat, mensagem in ROTEIRO:
            resposta = servico.enviar(chat, "usuario-demo", f"demo-{chat}", mensagem)
            print("=" * 100)
            print(f"[{chat}] {mensagem}")
            print(f"tipo: {resposta.tipo} | áreas: {resposta.areas} | reescrita: {resposta.reescrita} | "
                  f"Sincronizador: {resposta.modo_sincronizacao}")
            for area, r in resposta.respostas.items():
                print(f"  {area}: modelo {r.model_used}, guardrail {r.intent_category}, "
                      f"{len(r.retrieved_chunks)} Trechos, {len(r.citations)} citações")
            print("-" * 100)
            print(resposta.texto)
            for citacao in resposta.citacoes:
                print(f"  - {citacao[:160]}")
            print()


if __name__ == "__main__":
    main()
