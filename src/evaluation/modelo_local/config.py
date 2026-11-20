"""Parâmetros da comparação de modelos locais (issue #55), sobrescrevíveis por variável de ambiente."""

from __future__ import annotations

import os

from src.config import DATA_DIR, PROJECT_ROOT

EVAL_DIR = PROJECT_ROOT / "eval" / "modelo_local"
ENTRADAS_PATH = EVAL_DIR / "entradas.json"
FERRAMENTAS_CASOS_PATH = EVAL_DIR / "ferramentas.json"
JUIZ_VALIDACAO_PATH = EVAL_DIR / "juiz_validacao.json"
RESULTADOS_JSON_PATH = EVAL_DIR / "resultados.json"
RESULTADOS_MD_PATH = EVAL_DIR / "resultados.md"
# Saídas brutas (grandes e regeneráveis): fora do Git.
BRUTOS_DIR = DATA_DIR / "modelo_local"

# Instância do Ollama usada na medição. A padrão do projeto é a 11434; a comparação usa uma
# instância restrita à GPU de referência (8 GB), para o resultado valer para essa máquina.
OLLAMA_URL = os.getenv("MODELO_LOCAL_OLLAMA_URL", "http://127.0.0.1:11435")
# Vazio na GPU de referência. Em outra máquina, o nome dela vai em cada geração, e essas gerações
# entram nas métricas de qualidade, mas não na latência, nos tokens por segundo nem na memória.
MAQUINA = os.getenv("MODELO_LOCAL_MAQUINA", "")

# Candidatos (o qwen2.5:7b atual é a referência). Decisão de 13/11/2026: não há lista de reserva;
# o modelo de reserva é o 2º colocado entre estes.
CANDIDATOS = ["qwen2.5:7b", "qwen3.5:9b", "gemma4:e4b", "llama3.1:8b", "mistral-nemo:12b"]

# Condições iguais para todos: as mesmas da produção (`llm_client.py`), com semente fixa por execução.
SEMENTES = [1, 2, 3]
TEMPERATURA = 0.1
NUM_CTX = int(os.getenv("MODELO_LOCAL_NUM_CTX", "8192"))
NUM_PREDICT = 1024
TIMEOUT = float(os.getenv("MODELO_LOCAL_TIMEOUT", "180"))

# Juiz: outra família que nenhum candidato (ADR 0003: perguntas sintéticas e Trechos públicos).
# O juiz da Groq foi validado e usado até 13/11/2026; o limite diário de tokens do plano gratuito
# inviabilizou a medição, e o julgamento passou a subagentes do Claude, às cegas (cego.py).
JUIZ_MODELO = os.getenv("MODELO_LOCAL_JUIZ", "claude-sonnet (subagente, às cegas)")
JUIZ_MODELO_GROQ = "openai/gpt-oss-120b"
JUIZ_SEMENTE = 1
# O juiz avalia a semente 1 de todos os candidatos e as sementes 2 e 3 só dos dois finalistas
# (limite de 1.000 chamadas por dia no plano gratuito da Groq).
SEMENTES_JUIZ_TODOS = [1]
SEMENTES_JUIZ_FINALISTAS = [2, 3]
# O plano gratuito também limita o juiz a 200 mil tokens por dia (cerca de 85 julgamentos), então ele
# avalia todos os casos de segurança e uma amostra estratificada por tipo dos demais, a mesma para
# todos os candidatos (decisão de 13/11/2026). As métricas automáticas continuam nos 96 casos.
AMOSTRA_JUIZ = int(os.getenv("MODELO_LOCAL_AMOSTRA_JUIZ", "30"))
AMOSTRA_JUIZ_SEMENTE = 55
