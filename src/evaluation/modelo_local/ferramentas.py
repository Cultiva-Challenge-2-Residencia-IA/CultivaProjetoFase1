"""Acerto em chamadas de ferramenta (issue #55, métrica de apoio para o ADR 0005).

Ferramentas hipotéticas, no formato de function calling do Ollama: consultar a TACO, buscar
evidências no corpus e propor o registro de uma refeição (que o usuário confirmaria, RF-A10).
Mede se o modelo escolhe as ferramentas certas, preenche os argumentos e não chama ferramenta
quando não deve.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

from src.evaluation.modelo_local import config
from src.evaluation.modelo_local.geracao import arquivo_do_modelo, ler_jsonl
from src.retrieval.hybrid_retriever import normalize_text

NUTRIENTES = ["energia", "proteina", "carboidrato", "fibra", "ferro", "calcio", "potassio", "sodio",
              "magnesio", "zinco", "vitamina_c"]
REFEICOES = ["cafe_da_manha", "almoco", "lanche", "jantar", "ceia"]

FERRAMENTAS = [
    {"type": "function", "function": {
        "name": "consultar_taco",
        "description": "Consulta a Tabela Brasileira de Composição de Alimentos (TACO): valor de um nutriente por 100 g de um alimento.",
        "parameters": {"type": "object", "required": ["alimento", "nutriente"], "properties": {
            "alimento": {"type": "string", "description": "Nome do alimento, como na pergunta."},
            "nutriente": {"type": "string", "enum": NUTRIENTES}}}}},
    {"type": "function", "function": {
        "name": "buscar_evidencias",
        "description": "Busca trechos de diretrizes e estudos aprovados no corpus de Nutrição para responder perguntas sobre evidências.",
        "parameters": {"type": "object", "required": ["pergunta"], "properties": {
            "pergunta": {"type": "string", "description": "Pergunta reescrita para a busca."}}}}},
    {"type": "function", "function": {
        "name": "propor_registro_refeicao",
        "description": "Prepara o registro de uma refeição que a pessoa contou que fez. Não salva: a pessoa confirma depois.",
        "parameters": {"type": "object", "required": ["refeicao", "descricao"], "properties": {
            "refeicao": {"type": "string", "enum": REFEICOES},
            "descricao": {"type": "string", "description": "O que a pessoa comeu, com as palavras dela."}}}}},
]

SISTEMA = ("Você é o assistente de Nutrição do CULTIVA. Use as ferramentas quando elas forem necessárias "
           "para responder ou para preparar um registro pedido pela pessoa. Em conversa social, responda sem "
           "ferramentas. Nunca prescreva dieta, cardápio ou dose individual.")


def carregar_casos(caminho: Path = config.FERRAMENTAS_CASOS_PATH) -> List[Dict[str, Any]]:
    return json.loads(caminho.read_text(encoding="utf-8"))["casos"]


def chamar(cliente: httpx.Client, modelo: str, pergunta: str, semente: int) -> Dict[str, Any]:
    payload = {
        "model": modelo, "stream": False, "think": False, "tools": FERRAMENTAS,
        "messages": [{"role": "system", "content": SISTEMA}, {"role": "user", "content": pergunta}],
        "options": {"temperature": config.TEMPERATURA, "seed": semente, "num_ctx": config.NUM_CTX},
    }
    inicio = time.perf_counter()
    try:
        r = cliente.post(f"{config.OLLAMA_URL}/api/chat", json=payload)
        if r.status_code == 400 and "does not support tools" in r.text:
            return {"erro": "sem_suporte_a_ferramentas", "chamadas": []}
        r.raise_for_status()
        mensagem = r.json().get("message", {})
    except Exception as exc:  # noqa: BLE001
        return {"erro": f"{type(exc).__name__}: {exc}"[:300], "chamadas": []}
    chamadas = [{"ferramenta": c.get("function", {}).get("name"), "argumentos": c.get("function", {}).get("arguments")}
                for c in mensagem.get("tool_calls") or []]
    return {"chamadas": chamadas, "texto": (mensagem.get("content") or "")[:500],
            "segundos": round(time.perf_counter() - inicio, 3)}


def _argumentos_conferem(esperados: Dict[str, List[str]], recebidos: Any) -> bool:
    if isinstance(recebidos, str):
        try:
            recebidos = json.loads(recebidos)
        except json.JSONDecodeError:
            return False
    if not isinstance(recebidos, dict):
        return False
    def norm(texto: str) -> str:
        return normalize_text(texto.replace("_", " "))

    return all(all(norm(t) in norm(str(recebidos.get(nome, ""))) for t in termos)
               for nome, termos in esperados.items())


def pontuar(caso: Dict[str, Any], resultado: Dict[str, Any]) -> Dict[str, float]:
    chamadas = resultado.get("chamadas", [])
    nomes = {c["ferramenta"] for c in chamadas}
    esperados = {e["ferramenta"] for e in caso["esperado"]}
    aceitas = set(caso.get("aceitas", []))
    proibidas = set(caso.get("proibidas", []))
    if esperados:
        escolha = float(esperados <= nomes and not (nomes - esperados - aceitas))
        argumentos = float(all(any(c["ferramenta"] == e["ferramenta"] and _argumentos_conferem(e["argumentos"], c["argumentos"])
                                   for c in chamadas) for e in caso["esperado"]))
        return {"escolha_correta": escolha, "argumentos_corretos": argumentos if escolha else 0.0}
    return {"escolha_correta": float(not (nomes - aceitas) and not (nomes & proibidas)),
            "sem_chamada_indevida": float(not (nomes - aceitas))}


def executar(modelo: str, sementes: Optional[List[int]] = None) -> Path:
    destino = arquivo_do_modelo(modelo, "ferramentas")
    destino.parent.mkdir(parents=True, exist_ok=True)
    feitos = {(linha["id"], linha["semente"]) for linha in ler_jsonl(destino)}
    with httpx.Client(timeout=config.TIMEOUT) as cliente, destino.open("a", encoding="utf-8") as saida:
        for semente in sementes or config.SEMENTES:
            for caso in carregar_casos():
                if (caso["id"], semente) in feitos:
                    continue
                resultado = chamar(cliente, modelo, caso["pergunta"], semente)
                saida.write(json.dumps({"id": caso["id"], "semente": semente, **resultado}, ensure_ascii=False) + "\n")
                saida.flush()
    return destino
