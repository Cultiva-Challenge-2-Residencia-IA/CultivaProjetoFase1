"""Respostas do sistema atual para as perguntas do "não sei" (issue #52).

Para cada pergunta de `eval/abstencao/casos.json` e do golden set v2, roda o consultor de produção
com o mesmo Ollama dos candidatos e guarda a resposta, os Trechos recuperados e o "não sei" das
camadas locais. Os candidatos julgam essas respostas depois, sem gerar de novo.

As camadas locais são o piso: quando elas já deram "não sei" (ou o alerta de risco), nenhum
candidato é consultado, e a resposta continua "não sei".
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List

from src.config import ABSTENCAO_CASOS_PATH
from src.evaluation import benchmark_v2
from src.evaluation.comparacao_guardrails import config

RESPOSTAS_PATH = config.BRUTOS_DIR / "respostas.jsonl"


def perguntas() -> List[Dict[str, Any]]:
    """Abstenção (todos os splits; o `test` é o recorte oficial da issue) e golden v2."""
    dados = json.loads(Path(ABSTENCAO_CASOS_PATH).read_text(encoding="utf-8"))
    casos = dados["casos"] if isinstance(dados, dict) else dados
    itens = [{"id": c["id"], "conjunto": "abstencao", "split": c["split"], "tipo": c["tipo"],
              "esperado": c["esperado"], "pergunta": c["pergunta"]} for c in casos]
    for c in benchmark_v2.carregar_casos():
        if c.get("comportamento_esperado") == "responder":
            itens.append({"id": c["id"], "conjunto": "golden_v2", "split": c["split"], "tipo": c["tipo"],
                          "esperado": "responder", "pergunta": c["pergunta"]})
    return itens


def ler(caminho: Path = RESPOSTAS_PATH) -> List[Dict[str, Any]]:
    if not caminho.exists():
        return []
    return [json.loads(linha) for linha in caminho.read_text(encoding="utf-8").splitlines() if linha.strip()]


def texto(resposta: Any) -> str:
    """Texto da resposta sem os marcadores de citação ([T1], [GRAFO], [TACO]) da #12: o candidato
    julga o conteúdo contra os Trechos, e os marcadores só atrapalhariam os frameworks."""
    import re

    partes = [resposta.evidence_summary, resposta.physiological_mechanism, resposta.protocol_findings]
    juntas = "\n\n".join(p for p in partes if p and p.strip())
    return re.sub(r"\s*\[(?:T\d+|GRAFO|TACO)\]", "", juntas)


def gerar(caminho: Path = RESPOSTAS_PATH) -> Path:
    from src.agent.consultant_baseline import NutritionConsultantBaseline

    consultor = NutritionConsultantBaseline(enable_ollama=True)
    consultor.llm_client.base_url = config.OLLAMA_URL
    consultor.llm_client.primary_model = config.MODELO
    consultor.llm_client.fallback_model = ""
    consultor.llm_client.provider = "ollama"
    if not consultor.llm_client.is_ollama_available():
        raise SystemExit(f"Ollama indisponível em {config.OLLAMA_URL}.")
    feitos = {r["id"] for r in ler(caminho)}
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("a", encoding="utf-8") as saida:
        for p in perguntas():
            if p["id"] in feitos:
                continue
            inicio = time.perf_counter()
            r = consultor.consult(p["pergunta"])
            linha = {
                **p,
                "segundos_geracao": round(time.perf_counter() - inicio, 2),
                "modelo": r.model_used,
                # "extrativa_apos_citacao_invalida": a resposta do LLM foi bloqueada pela #12 e
                # trocada pela síntese extrativa, que é sustentada por construção.
                "fundamentacao_status": getattr(r, "fundamentacao_status", None),
                "nao_sei_local": bool(r.abstencao),
                "risco": bool(r.risk_triggered),
                "resposta": texto(r),
                "trechos": [rc.chunk.raw_text for rc in r.retrieved_chunks],
                "maquina": config.MAQUINA or None,
            }
            saida.write(json.dumps(linha, ensure_ascii=False) + "\n")
            saida.flush()
            print(f"{p['id']:14s} {linha['modelo']:28s} {linha['segundos_geracao']:6.1f} s", flush=True)
    return caminho
