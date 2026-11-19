"""Congela as entradas da síntese: o mesmo prompt para todos os candidatos (issue #55).

A recuperação, a TACO e o grafo rodam uma vez, no modo sem LLM, e o prompt que iria ao modelo é
gravado com os textos de contexto que o juiz usa para verificar a fidelidade. Assim a comparação
mede só a geração.

Perguntas: golden v2 (todas as que chegam à síntese), as perguntas "dentro" do conjunto do
"não sei" e o benchmark v1. Perguntas barradas antes da síntese (risco, injeção, "não sei") não
chegam ao modelo e ficam de fora, com o motivo registrado.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List

from src.config import ABSTENCAO_CASOS_PATH, BENCHMARK_QUESTIONS_PATH, GOLDEN_V2_DIR
from src.evaluation.modelo_local.config import ENTRADAS_PATH


def _perguntas() -> List[Dict[str, Any]]:
    perguntas: List[Dict[str, Any]] = []
    for split in ("dev", "test"):
        dados = json.loads((GOLDEN_V2_DIR / f"{split}.json").read_text(encoding="utf-8"))
        for caso in dados["casos"]:
            perguntas.append({
                "id": caso["id"],
                "origem": "golden_v2",
                "tipo": caso["tipo"],
                "split": caso["split"],
                "pergunta": caso["pergunta"],
                "termos_obrigatorios": (caso.get("geracao") or {}).get("termos_obrigatorios") or [],
                "termos_proibidos": (caso.get("geracao") or {}).get("termos_proibidos") or [],
            })
    abstencao = json.loads(ABSTENCAO_CASOS_PATH.read_text(encoding="utf-8"))["casos"]
    for caso in abstencao:
        if caso["tipo"] == "dentro":
            perguntas.append({"id": caso["id"], "origem": "abstencao", "tipo": "dentro", "split": caso["split"],
                              "pergunta": caso["pergunta"], "termos_obrigatorios": [], "termos_proibidos": []})
    for caso in json.loads(BENCHMARK_QUESTIONS_PATH.read_text(encoding="utf-8")):
        perguntas.append({
            "id": caso["id"], "origem": "benchmark_v1",
            "tipo": "prescricao" if caso.get("expect_guardrail_trigger") else caso.get("category", "v1"),
            "split": "dev", "pergunta": caso["query"],
            "termos_obrigatorios": [[t] for t in caso.get("expected_keywords", [])], "termos_proibidos": []})
    return perguntas


def congelar(caminho: Path = ENTRADAS_PATH) -> Dict[str, Any]:
    from src.agent.consultant_baseline import NutritionConsultantBaseline

    consultor = NutritionConsultantBaseline(enable_ollama=False)
    cliente = consultor.llm_client
    original = cliente.generate_structured_synthesis
    capturado: Dict[str, Any] = {}

    def capturar(query, retrieved_chunks, taco_context_str="", graph_context_str=""):
        capturado.update(
            query=query,
            user_prompt=cliente._build_user_prompt(query, retrieved_chunks, taco_context_str, graph_context_str),
            trechos=[{"id": r.chunk.chunk_id, "doc_id": r.chunk.doc_id, "texto": r.chunk.raw_text}
                     for r in retrieved_chunks],
            taco=taco_context_str,
            grafo=graph_context_str,
        )
        return original(query, retrieved_chunks, taco_context_str=taco_context_str,
                        graph_context_str=graph_context_str)

    cliente.generate_structured_synthesis = capturar
    casos, fora = [], []
    vistos = set()
    for pergunta in _perguntas():
        if pergunta["pergunta"] in vistos:
            fora.append({"id": pergunta["id"], "motivo": "pergunta repetida"})
            continue
        vistos.add(pergunta["pergunta"])
        capturado.clear()
        resposta = consultor.consult(pergunta["pergunta"])
        if not capturado:
            fora.append({"id": pergunta["id"], "motivo": resposta.retrieval_mode})
            continue
        casos.append({**pergunta, **capturado, "guardrail_entrada": resposta.guardrail_triggered})

    dados = {
        "descricao": "Prompts congelados da síntese (issue #55). Gerado por `python -m "
                     "src.evaluation.modelo_local congelar`; não edite à mão.",
        "corpus_version": getattr(consultor, "corpus_version", None) or _impressao(consultor.chunks),
        "casos": casos,
        "fora_da_sintese": fora,
    }
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(dados, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return dados


def _impressao(chunks: List[Any]) -> str:
    h = hashlib.sha256()
    for c in sorted(chunks, key=lambda c: c.chunk_id):
        h.update(c.chunk_id.encode())
        h.update(c.raw_text.encode())
    return h.hexdigest()[:16]


def carregar(caminho: Path = ENTRADAS_PATH) -> List[Dict[str, Any]]:
    return json.loads(caminho.read_text(encoding="utf-8"))["casos"]
