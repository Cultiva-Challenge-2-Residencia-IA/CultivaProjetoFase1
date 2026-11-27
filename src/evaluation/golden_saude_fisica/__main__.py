"""CLI do golden set de Saúde Física: `validar`, `estatisticas` e `avaliar`."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Dict

from src.evaluation.golden_saude_fisica.avaliador import avaliar_golden
from src.evaluation.golden_saude_fisica.estatisticas import calcular_estatisticas
from src.evaluation.golden_saude_fisica.validador import (
    GOLDEN_SAUDE_FISICA_DIR,
    carregar_split,
    serializar_split_deterministico,
    validar_golden,
)


def _executar_consultor_local(sem_llm: bool) -> Any:
    from src.agents.fisica.consultor import ConsultorSaudeFisica
    from src.orquestrador.roteamento import rotear_por_regras

    consultor = ConsultorSaudeFisica(enable_ollama=not sem_llm)

    def _rodar(caso: Dict[str, Any]) -> Dict[str, Any]:
        pergunta = caso["pergunta"]
        if caso["tipo"] == "entre_abas":
            rota = rotear_por_regras(pergunta)
            if rota.estudos:
                texto = (
                    "Essa pergunta pertence à área de Estudos, que ainda não está implementada "
                    "no CULTIVA."
                )
            else:
                texto = (
                    "A pergunta envolve as áreas: "
                    + ", ".join(rota.areas or ["não identificadas pelas regras"])
                    + "."
                )
            return {
                "resposta": texto,
                "roteamento_obtido": {"areas": rota.areas, "estudos": rota.estudos},
            }

        resp = consultor.consult(pergunta)
        fontes = [c.chunk.doc_id for c in resp.retrieved_chunks]
        trechos = [c.chunk.chunk_id for c in resp.retrieved_chunks]
        texto_resp = resp.evidence_summary
        if resp.protocol_findings:
            texto_resp = f"{texto_resp}\n\n{resp.protocol_findings}".strip()
        return {
            "resposta": texto_resp,
            "fontes_recuperadas": fontes,
            "trechos_recuperados": trechos,
            "guardrail_acionado": resp.guardrail_triggered,
            "abstencao": resp.abstencao,
            "citacoes": resp.citations,
        }

    return _rodar


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m src.evaluation.golden_saude_fisica",
        description="Validação, estatísticas e avaliação do golden set de Saúde Física.",
    )
    sub = parser.add_subparsers(dest="comando", required=True)

    p_val = sub.add_parser("validar", help="Valida schema, evidências no corpus e sem vazamento.")
    p_val.add_argument("--diretorio", type=Path, default=GOLDEN_SAUDE_FISICA_DIR)
    p_val.add_argument(
        "--incluir-test",
        action="store_true",
        help="Inclui test.json na validação e verifica sobreposição dev/test (holdout).",
    )
    p_val.add_argument(
        "--ordenar",
        action="store_true",
        help="Regrava os JSONs lidos de forma determinística (ordenados por id, UTF-8, LF).",
    )

    p_est = sub.add_parser("estatisticas", help="Exibe contagens por tipo, tema, dificuldade e fonte.")
    p_est.add_argument("--diretorio", type=Path, default=GOLDEN_SAUDE_FISICA_DIR)
    p_est.add_argument(
        "--incluir-test",
        action="store_true",
        help="Inclui test.json nas estatísticas (holdout).",
    )

    p_av = sub.add_parser(
        "avaliar",
        help="Avalia recuperação e qualidade das respostas frente ao modelo ideal do golden.",
    )
    p_av.add_argument("--diretorio", type=Path, default=GOLDEN_SAUDE_FISICA_DIR)
    p_av.add_argument("--split", choices=("dev", "test"), default="dev")
    p_av.add_argument(
        "--incluir-test",
        action="store_true",
        help="Obrigatório para avaliar o split 'test' (holdout).",
    )
    p_av.add_argument("--respostas", type=Path, default=None, help="JSON com respostas pré-geradas por id.")
    p_av.add_argument("--sem-llm", action="store_true", help="Executa ConsultorSaudeFisica sem Ollama.")
    p_av.add_argument("--saida", type=Path, default=None, help="Arquivo opcional para salvar o relatório JSON.")

    args = parser.parse_args(argv)

    if args.comando == "validar":
        if args.ordenar:
            splits = ("dev", "test") if args.incluir_test else ("dev",)
            for s in splits:
                caminho = args.diretorio / f"{s}.json"
                if caminho.exists():
                    dados = carregar_split(s, args.diretorio)
                    caminho.write_text(serializar_split_deterministico(dados), encoding="utf-8", newline="\n")
        res = validar_golden(diretorio=args.diretorio, incluir_test=args.incluir_test)
        for aviso in res.avisos:
            print(f"AVISO: {aviso}", file=sys.stderr)
        if not res.ok:
            for erro in res.erros:
                print(f"ERRO: {erro}", file=sys.stderr)
            return 1
        print(f"OK: golden set de Saúde Física válido ({res.casos_por_split}).")
        return 0

    if args.comando == "estatisticas":
        stats = calcular_estatisticas(diretorio=args.diretorio, incluir_test=args.incluir_test)
        print(json.dumps(stats, ensure_ascii=False, indent=2))
        return 0

    if args.comando == "avaliar":
        if args.respostas is not None:
            respostas_por_id = json.loads(args.respostas.read_text(encoding="utf-8"))
            relatorio = avaliar_golden(
                split=args.split,
                incluir_test=args.incluir_test,
                diretorio=args.diretorio,
                respostas_por_id=respostas_por_id,
            )
        else:
            relatorio = avaliar_golden(
                split=args.split,
                incluir_test=args.incluir_test,
                diretorio=args.diretorio,
                executor=_executar_consultor_local(sem_llm=args.sem_llm),
            )
        texto_rel = json.dumps(relatorio, ensure_ascii=False, indent=2) + "\n"
        if args.saida is not None:
            args.saida.parent.mkdir(parents=True, exist_ok=True)
            args.saida.write_text(texto_rel, encoding="utf-8", newline="\n")
        print(json.dumps({"split": relatorio["split"], "total_casos": relatorio["total_casos"], "metricas": relatorio["metricas"]}, ensure_ascii=False, indent=2))
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
