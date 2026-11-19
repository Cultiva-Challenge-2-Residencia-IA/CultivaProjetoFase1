"""Geração com cada candidato sobre os prompts congelados (issue #55).

Cada (caso, semente) vira uma linha em `data/modelo_local/geracoes/<modelo>.jsonl`. A execução é
retomável: linhas já gravadas não são refeitas. O modo de raciocínio ("thinking") fica desligado
em todos, como na produção, que pede JSON direto.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

from src.agent.llm_client import SYSTEM_PROMPT_CONSULTANT
from src.evaluation.modelo_local import config

CAMPOS_ESQUEMA = {
    "evidence_summary": str,
    "physiological_mechanism": str,
    "protocol_findings": str,
    "food_sources_or_compounds": list,
    "evidence_grade": str,
}


def arquivo_do_modelo(modelo: str, pasta: str = "geracoes") -> Path:
    return config.BRUTOS_DIR / pasta / f"{modelo.replace(':', '_').replace('/', '_')}.jsonl"


def ler_jsonl(caminho: Path) -> List[Dict[str, Any]]:
    if not caminho.exists():
        return []
    return [json.loads(linha) for linha in caminho.read_text(encoding="utf-8").splitlines() if linha.strip()]


def validar_esquema(conteudo: str) -> Dict[str, Any]:
    """JSON válido e com os cinco campos do consultor nos tipos certos."""
    try:
        dados = json.loads(conteudo)
    except (json.JSONDecodeError, TypeError):
        return {"json_valido": False, "esquema_valido": False, "saida": None}
    esquema = isinstance(dados, dict) and all(
        isinstance(dados.get(campo), tipo) for campo, tipo in CAMPOS_ESQUEMA.items())
    return {"json_valido": True, "esquema_valido": bool(esquema), "saida": dados if isinstance(dados, dict) else None}


def chamar(cliente: httpx.Client, modelo: str, user_prompt: str, semente: int) -> Dict[str, Any]:
    payload = {
        "model": modelo,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT_CONSULTANT},
            {"role": "user", "content": user_prompt},
        ],
        "format": "json",
        "stream": False,
        "think": False,
        "options": {"temperature": config.TEMPERATURA, "seed": semente,
                    "num_ctx": config.NUM_CTX, "num_predict": config.NUM_PREDICT},
    }
    inicio = time.perf_counter()
    try:
        resposta = cliente.post(f"{config.OLLAMA_URL}/api/chat", json=payload)
        resposta.raise_for_status()
        dados = resposta.json()
    except httpx.TimeoutException:
        return {"erro": "timeout", "segundos": round(time.perf_counter() - inicio, 3)}
    except Exception as exc:  # noqa: BLE001 - qualquer falha conta como erro de robustez
        return {"erro": f"{type(exc).__name__}: {exc}"[:300], "segundos": round(time.perf_counter() - inicio, 3)}
    conteudo = dados.get("message", {}).get("content", "")
    return {
        "conteudo": conteudo,
        "segundos": round(time.perf_counter() - inicio, 3),
        "tokens_prompt": dados.get("prompt_eval_count"),
        "tokens_saida": dados.get("eval_count"),
        "duracao_saida_ns": dados.get("eval_duration"),
        "duracao_prompt_ns": dados.get("prompt_eval_duration"),
        "truncada": dados.get("done_reason") == "length",
        **{k: v for k, v in validar_esquema(conteudo).items() if k != "saida"},
    }


def info_do_modelo(cliente: httpx.Client, modelo: str) -> Dict[str, Any]:
    """Digest, quantização e memória ocupada (após o aquecimento)."""
    show = cliente.post(f"{config.OLLAMA_URL}/api/show", json={"model": modelo}).json()
    ps = cliente.get(f"{config.OLLAMA_URL}/api/ps").json().get("models", [])
    carregado = next((m for m in ps if m.get("name") == modelo or m.get("model") == modelo), {})
    detalhes = show.get("details", {})
    tags = cliente.get(f"{config.OLLAMA_URL}/api/tags").json().get("models", [])
    digest = next((m.get("digest") for m in tags if m.get("name") == modelo), None)
    return {
        "modelo": modelo,
        "digest": digest,
        "familia": detalhes.get("family"),
        "parametros": detalhes.get("parameter_size"),
        "quantizacao": detalhes.get("quantization_level"),
        "licenca_resumo": (show.get("license") or "").strip().splitlines()[0][:160] if show.get("license") else None,
        "capacidades": show.get("capabilities"),
        "memoria_total_bytes": carregado.get("size"),
        "memoria_vram_bytes": carregado.get("size_vram"),
    }


def gerar(modelo: str, casos: List[Dict[str, Any]], sementes: Optional[List[int]] = None) -> Path:
    sementes = sementes or config.SEMENTES
    destino = arquivo_do_modelo(modelo)
    destino.parent.mkdir(parents=True, exist_ok=True)
    feitos = {(linha["id"], linha["semente"]) for linha in ler_jsonl(destino)}
    with httpx.Client(timeout=config.TIMEOUT) as cliente:
        # Aquecimento: carrega o modelo fora das medições e registra a memória ocupada.
        inicio = time.perf_counter()
        chamar(cliente, modelo, casos[0]["user_prompt"], 0)
        info = {**info_do_modelo(cliente, modelo), "carga_segundos": round(time.perf_counter() - inicio, 2)}
        if not config.MAQUINA:
            # A memória e o tempo de carga só valem na máquina de referência.
            info_path = arquivo_do_modelo(modelo, "info").with_suffix(".json")
            info_path.parent.mkdir(parents=True, exist_ok=True)
            info_path.write_text(json.dumps(info, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        with destino.open("a", encoding="utf-8") as saida:
            for semente in sementes:
                for caso in casos:
                    if (caso["id"], semente) in feitos:
                        continue
                    resultado = chamar(cliente, modelo, caso["user_prompt"], semente)
                    maquina = {"maquina": config.MAQUINA} if config.MAQUINA else {}
                    saida.write(json.dumps({"id": caso["id"], "semente": semente, **resultado, **maquina},
                                           ensure_ascii=False) + "\n")
                    saida.flush()
    return destino
