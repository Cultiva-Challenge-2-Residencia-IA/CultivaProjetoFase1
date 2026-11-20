"""Parâmetros da comparação de frameworks de guardrail (issue #52)."""

from __future__ import annotations

import os

from src.config import DATA_DIR, OLLAMA_BASE_URL, OLLAMA_MODEL, PROJECT_ROOT

EVAL_DIR = PROJECT_ROOT / "eval" / "comparacao_guardrails"
CASOS_FUNDAMENTACAO_PATH = EVAL_DIR / "casos_fundamentacao.json"
RESULTADOS_JSON_PATH = EVAL_DIR / "resultados.json"
RESULTADOS_MD_PATH = EVAL_DIR / "resultados.md"
# Respostas geradas e vereditos brutos (grandes e regeneráveis): fora do Git.
BRUTOS_DIR = DATA_DIR / "comparacao_guardrails"

# O mesmo LLM local para os três candidatos e para gerar as respostas (Ollama, ADR 0003): o
# `OLLAMA_MODEL` de produção, `gemma4:e4b` desde o ADR 0004.
OLLAMA_URL = os.getenv("COMPARACAO_GUARDRAILS_OLLAMA_URL", OLLAMA_BASE_URL).rstrip("/")
MODELO = os.getenv("COMPARACAO_GUARDRAILS_MODELO", OLLAMA_MODEL)
# Máquina da medição. Fora da GPU de referência, o tempo por pergunta é só indicativo.
MAQUINA = os.getenv("COMPARACAO_GUARDRAILS_MAQUINA", "")
TEMPERATURA = 0.0
SEMENTE = 52
NUM_CTX = 8192
TIMEOUT = float(os.getenv("COMPARACAO_GUARDRAILS_TIMEOUT", "600"))

CANDIDATOS = ["direto_pre", "direto_pos", "nemo", "guardrails_ai"]
