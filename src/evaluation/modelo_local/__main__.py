"""Linha de comando da comparação de modelos locais (issue #55).

    uv run python -m src.evaluation.modelo_local congelar
    uv run python -m src.evaluation.modelo_local gerar [--modelos qwen2.5:7b ...]
    uv run python -m src.evaluation.modelo_local ferramentas [--modelos ...]
    uv run python -m src.evaluation.modelo_local validar-juiz
    uv run python -m src.evaluation.modelo_local julgar                     # semente 1 de todos
    uv run python -m src.evaluation.modelo_local julgar --finalistas        # sementes 2 e 3 dos 2 primeiros
    uv run python -m src.evaluation.modelo_local bertscore [--modelos ...]   # uv sync --group modelo-local
    uv run python -m src.evaluation.modelo_local relatorio
    # Juiz às cegas por subagentes do Claude (substitui o da Groq; ver cego.py)
    uv run python -m src.evaluation.modelo_local exportar-cego --fase s1|finalistas|concordancia
    uv run python -m src.evaluation.modelo_local importar-cego --fase s1|finalistas|concordancia
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import List

from src.evaluation.modelo_local import cego, config, entradas, ferramentas, geracao, juiz, relatorio


def _modelos(args: argparse.Namespace) -> List[str]:
    return args.modelos or config.CANDIDATOS


def _julgar(modelos: List[str], sementes: List[int]) -> None:
    j = juiz.Juiz()
    casos = {c["id"]: c for c in entradas.carregar()}
    amostra = set(juiz.amostra_do_juiz(list(casos.values())))
    for modelo in modelos:
        destino = geracao.arquivo_do_modelo(modelo, "juiz")
        destino.parent.mkdir(parents=True, exist_ok=True)
        feitos = {(x["id"], x["semente"]) for x in geracao.ler_jsonl(destino) if "erro_juiz" not in x}
        with destino.open("a", encoding="utf-8") as saida:
            for g in geracao.ler_jsonl(geracao.arquivo_do_modelo(modelo)):
                if g["semente"] not in sementes or (g["id"], g["semente"]) in feitos or not g.get("esquema_valido") \
                        or g["id"] not in amostra:
                    continue
                caso = casos[g["id"]]
                resposta = juiz.texto_da_resposta(json.loads(g["conteudo"]))
                veredito = j.avaliar(caso["pergunta"], juiz.contexto_do_caso(caso), resposta)
                saida.write(json.dumps({"id": g["id"], "semente": g["semente"], **veredito}, ensure_ascii=False) + "\n")
                saida.flush()
        print(f"{modelo}: julgado. Limites da Groq: {j.limites}")


def _bertscore(modelos: List[str]) -> None:
    from src.evaluation.modelo_local.metricas import bertscore, texto_completo

    casos = {c["id"]: c for c in entradas.carregar()}
    for modelo in modelos:
        destino = geracao.arquivo_do_modelo(modelo, "bertscore")
        destino.parent.mkdir(parents=True, exist_ok=True)
        feitos = {(x["id"], x["semente"]) for x in geracao.ler_jsonl(destino)}
        pendentes = [g for g in geracao.ler_jsonl(geracao.arquivo_do_modelo(modelo))
                     if g.get("esquema_valido") and (g["id"], g["semente"]) not in feitos
                     and casos.get(g["id"], {}).get("trechos")]
        if not pendentes:
            continue
        respostas = [texto_completo(json.loads(g["conteudo"])) for g in pendentes]
        referencias = [[t["texto"] for t in casos[g["id"]]["trechos"]] for g in pendentes]
        with destino.open("a", encoding="utf-8") as saida:
            for g, nota in zip(pendentes, bertscore(respostas, referencias)):
                saida.write(json.dumps({"id": g["id"], "semente": g["semente"], **nota}) + "\n")
        print(f"{modelo}: BERTScore de {len(pendentes)} respostas.")


def _validar_juiz() -> int:
    casos = {c["id"]: c for c in entradas.carregar()}
    if config.JUIZ_VALIDACAO_PATH.exists():
        dados = json.loads(config.JUIZ_VALIDACAO_PATH.read_text(encoding="utf-8"))
    else:
        dados = juiz.montar_validacao(list(casos.values()))
    j = juiz.Juiz()
    por_tipo: dict = {}
    for item in dados["itens"]:
        veredito = j.avaliar(item["pergunta"], juiz.contexto_do_caso(casos[item["caso"]]), item["resposta"])
        item["veredito"] = veredito
        item["correto"] = juiz.item_correto(item, veredito)
        por_tipo.setdefault(item["tipo"], []).append(item["correto"])
    dados["juiz"] = config.JUIZ_MODELO_GROQ
    dados["criterios"] = juiz.CRITERIOS_VALIDACAO
    dados["acerto_por_tipo"] = {t: round(sum(v) / len(v), 4) for t, v in por_tipo.items()}
    dados["aprovado"] = all(a >= juiz.CRITERIOS_VALIDACAO["acerto_minimo"] for a in dados["acerto_por_tipo"].values())
    config.JUIZ_VALIDACAO_PATH.write_text(json.dumps(dados, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"Juiz {config.JUIZ_MODELO_GROQ}: acerto por tipo {dados['acerto_por_tipo']} -> "
          f"{'APROVADO' if dados['aprovado'] else 'REPROVADO'}")
    return 0 if dados["aprovado"] else 1


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Comparação de modelos locais (issue #55).")
    sub = parser.add_subparsers(dest="comando", required=True)
    sub.add_parser("congelar")
    for nome in ("gerar", "ferramentas", "julgar", "bertscore", "relatorio"):
        p = sub.add_parser(nome)
        p.add_argument("--modelos", nargs="+")
        p.add_argument("--sementes", nargs="+", type=int, default=None)
        if nome == "julgar":
            p.add_argument("--finalistas", action="store_true",
                           help="Julga as sementes 2 e 3 dos dois primeiros da classificação atual.")
    sub.add_parser("validar-juiz")
    for nome in ("exportar-cego", "importar-cego"):
        p = sub.add_parser(nome)
        p.add_argument("--fase", required=True, choices=["s1", "finalistas", "concordancia"])
        p.add_argument("--modelos", nargs="+")
    sub.add_parser("descartar-juiz-groq")
    args = parser.parse_args(argv)

    if args.comando == "congelar":
        dados = entradas.congelar()
        print(f"{len(dados['casos'])} prompts congelados; {len(dados['fora_da_sintese'])} fora da síntese.")
    elif args.comando == "gerar":
        casos = entradas.carregar()
        for modelo in _modelos(args):
            print(f"Gerando com {modelo}...", flush=True)
            geracao.gerar(modelo, casos, args.sementes or config.SEMENTES)
    elif args.comando == "ferramentas":
        for modelo in _modelos(args):
            print(f"Ferramentas com {modelo}...", flush=True)
            ferramentas.executar(modelo, args.sementes or config.SEMENTES)
    elif args.comando == "julgar":
        if args.finalistas:
            finalistas = relatorio.montar(_modelos(args))["classificacao"][:2]
            print(f"Finalistas: {finalistas}")
            _julgar(finalistas, args.sementes or config.SEMENTES_JUIZ_FINALISTAS)
        else:
            _julgar(_modelos(args), args.sementes or config.SEMENTES_JUIZ_TODOS)
    elif args.comando == "bertscore":
        _bertscore(_modelos(args))
    elif args.comando == "validar-juiz":
        return _validar_juiz()
    elif args.comando == "exportar-cego":
        if args.fase == "s1":
            modelos, sementes = _modelos(args), config.SEMENTES_JUIZ_TODOS
        elif args.fase == "finalistas":
            modelos = relatorio.montar(_modelos(args))["classificacao"][:2]
            sementes = config.SEMENTES_JUIZ_FINALISTAS
            print(f"Finalistas: {modelos}")
        else:
            modelos, sementes = _modelos(args), config.SEMENTES
        print(json.dumps(cego.exportar(args.fase, modelos, sementes), ensure_ascii=False, indent=1))
    elif args.comando == "importar-cego":
        print(json.dumps(cego.importar(args.fase), ensure_ascii=False, indent=1))
    elif args.comando == "descartar-juiz-groq":
        print(f"Movidos para juiz_groq_descartado/: {cego.descartar_juiz_anterior()}")
    elif args.comando == "relatorio":
        relatorio.gravar(_modelos(args))
        print(config.RESULTADOS_MD_PATH.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
