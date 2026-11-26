"""Avaliação do Projetor de contexto e dos Fatos do Usuário com o modelo real (issue #112).

Critérios escritos antes da medição: eval/projetor/criterios.md. Exige o Ollama local; fora do CI.

    uv run python -m src.evaluation.projetor extracao --split dev
    uv run python -m src.evaluation.projetor selecao --split dev
    uv run python -m src.evaluation.projetor resposta --split dev

Cada comando grava `eval/projetor/resultado_<comando>_<split>.json`.
"""

import argparse
import json
from pathlib import Path
import statistics
import sys
import tempfile
import time
from typing import Any, Dict, List

from src.agent.llm_json import ClienteJsonOllama
from src.chat.historico import HistoricoSQLite
from src.chat.servico import ServicoDeChat
from src.config import PROJECT_ROOT
from src.orquestrador.fatos import extrair_fatos
from src.orquestrador.roteamento import AREAS

PASTA = PROJECT_ROOT / "eval" / "projetor"


def _casos(arquivo: str, split: str) -> List[Dict[str, Any]]:
    return json.loads((PASTA / arquivo).read_text(encoding="utf-8"))[split]


def _gravar(nome: str, split: str, dados: Dict[str, Any]) -> None:
    destino = PASTA / f"resultado_{nome}_{split}.json"
    destino.write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(dados["resumo"], ensure_ascii=False, indent=2))
    print(f"Gravado em {destino.relative_to(PROJECT_ROOT)}")


def extracao(split: str, llm) -> None:
    casos, acertos, extraidos, esperadas_total, encontradas, falsos = [], 0, 0, 0, 0, 0
    for caso in _casos("extracao.json", split):
        fatos = extrair_fatos(caso["mensagem"], llm, caso["permitir_saude"])
        categorias = [c for c, _ in fatos]
        validas = set(caso["esperadas"]) | set(caso["aceitas"])
        acertos += sum(1 for c in categorias if c in validas)
        extraidos += len(categorias)
        esperadas_total += len(caso["esperadas"])
        encontradas += len(set(caso["esperadas"]) & set(categorias))
        falso = not caso["esperadas"] and bool(categorias)
        falsos += int(falso)
        casos.append({"id": caso["id"], "fatos": fatos, "esperadas": caso["esperadas"], "falso_fato": falso})
    _gravar("extracao", split, {"resumo": {
        "casos": len(casos),
        "precisao": round(acertos / extraidos, 3) if extraidos else None,
        "recall": round(encontradas / esperadas_total, 3) if esperadas_total else None,
        "falso_fato": falsos,
    }, "casos": casos})


class _AgenteQueRegistra:
    """Agente falso: a seleção só precisa saber o que cada agente recebeu."""

    def __init__(self) -> None:
        self.fatos: List[Any] = []

    def responder(self, pergunta, top_k, consultas_extras, historico, fatos=()):
        from src.models.schemas import ConsultantResponse

        self.fatos.extend(fatos)
        return ConsultantResponse(
            response_id="r", original_query=pergunta, effective_query=pergunta, guardrail_triggered=False,
            intent_category="SAFE_EVIDENCE_QUERY", evidence_summary="Resposta.", physiological_mechanism="",
            protocol_findings="", evidence_grade="N/A", corpus_version="c", prompt_version="p",
            model_version="m", fontes_version="f")


def _servico(pasta: Path, agentes, llm) -> ServicoDeChat:
    return ServicoDeChat(agentes=agentes, historico=HistoricoSQLite(pasta / "h.sqlite3"), llm=llm,
                         executar_em_segundo_plano=lambda tarefa: None)


def _preparar(servico: ServicoDeChat, caso: Dict[str, Any], memoria: bool) -> Dict[str, int]:
    """Guarda os fatos do caso e devolve o índice de cada fato pelo id gravado."""
    servico.definir_consentimento("u", memoria=memoria, saude=caso["saude"])
    for categoria, texto in caso["fatos"]:
        servico.fatos.registrar("u", "c0", categoria, texto, servico.relogio())
    textos = [t for _, t in caso["fatos"]]
    return {f.id: textos.index(f.texto) for f in servico.listar_fatos("u")}


def selecao(split: str, llm) -> None:
    casos, relacionados_total, relacionados_entregues, entregues_total, vazados = [], 0, 0, 0, 0
    for caso in _casos("selecao.json", split):
        with tempfile.TemporaryDirectory() as pasta:
            agentes = {area: _AgenteQueRegistra() for area in AREAS}
            servico = _servico(Path(pasta), agentes, llm)
            indice = _preparar(servico, caso, memoria=True)
            servico.enviar(caso["chat"], "u", "c1", caso["mensagem"])
            entregues = sorted({indice[f.id] for a in agentes.values() for f in a.fatos})
        relacionados, aceitos = set(caso["relacionados"]), set(caso["aceitos"])
        relacionados_total += len(relacionados)
        relacionados_entregues += len(relacionados & set(entregues))
        entregues_total += len(entregues)
        vazou = [i for i in entregues if i not in relacionados | aceitos]
        vazados += len(vazou)
        casos.append({"id": caso["id"], "entregues": entregues, "relacionados": sorted(relacionados),
                      "vazados": vazou})
    _gravar("selecao", split, {"resumo": {
        "casos": len(casos),
        "recall": round(relacionados_entregues / relacionados_total, 3) if relacionados_total else None,
        "vazamento": round(vazados / entregues_total, 3) if entregues_total else 0.0,
        "fatos_entregues": entregues_total,
    }, "casos": casos})


def resposta(split: str) -> None:
    from src.chat.fabrica import criar_servico

    casos, tempos = [], {"sem": [], "com": []}
    aceitas, usos, com_fato = {"sem": 0, "com": 0}, 0, 0
    selecionados = [c for c in _casos("selecao.json", split) if c["resposta"]]
    for caso in selecionados:
        registro: Dict[str, Any] = {"id": caso["id"], "mensagem": caso["mensagem"]}
        for modo in ("sem", "com"):
            with tempfile.TemporaryDirectory() as pasta:
                servico = criar_servico(enable_ollama=True, historico=HistoricoSQLite(Path(pasta) / "h.sqlite3"))
                servico.executar_em_segundo_plano = lambda tarefa: None
                _preparar(servico, caso, memoria=(modo == "com"))
                inicio = time.perf_counter()
                r = servico.enviar(caso["chat"], "u", "c1", caso["mensagem"])
                tempos[modo].append(time.perf_counter() - inicio)
            status = [getattr(resp, "fundamentacao_status", None) for resp in r.respostas.values()]
            aceita = any(s == "llm_citacoes_validas" for s in status)
            aceitas[modo] += int(aceita)
            registro[modo] = {"texto_com_marcadores": r.texto_com_marcadores, "fatos_usados": r.fatos_usados,
                              "status": status, "segundos": round(tempos[modo][-1], 1)}
            if modo == "com" and r.fatos_usados:
                com_fato += 1
                usos += int("[CONTEXTO]" in r.texto_com_marcadores)
        casos.append(registro)
    n = len(selecionados)
    _gravar("resposta", split, {"resumo": {
        "casos": n,
        "uso": round(usos / com_fato, 3) if com_fato else None,
        "casos_com_fato_entregue": com_fato,
        "aceitas_sem_memoria": round(aceitas["sem"] / n, 3) if n else None,
        "aceitas_com_memoria": round(aceitas["com"] / n, 3) if n else None,
        "mediana_s_sem_memoria": round(statistics.median(tempos["sem"]), 1) if n else None,
        "mediana_s_com_memoria": round(statistics.median(tempos["com"]), 1) if n else None,
        "condicao_de_saude": "julgar à mão as frases com [CONTEXTO] dos casos com condicao_saude",
    }, "casos": casos})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("comando", choices=["extracao", "selecao", "resposta"])
    parser.add_argument("--split", choices=["dev", "test"], default="dev")
    args = parser.parse_args()
    llm = ClienteJsonOllama("avaliacao_projetor", timeout=120.0)
    if not llm.disponivel():
        print("Ollama indisponível: esta avaliação exige o modelo local.", file=sys.stderr)
        return 1
    if args.comando == "extracao":
        extracao(args.split, llm)
    elif args.comando == "selecao":
        selecao(args.split, llm)
    else:
        resposta(args.split)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
