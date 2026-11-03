# Tudo roda a partir do ambiente local do repositório (ver scripts/bootstrap.sh).
export UV_PYTHON_INSTALL_DIR := $(CURDIR)/.python
export UV_CACHE_DIR := $(CURDIR)/.uv-cache
export UV_PYTHON_PREFERENCE := only-managed
export PYTHONPATH := $(CURDIR)/src

UV := $(CURDIR)/.uv/bin/uv
# Usa "docker compose" se existir; senão, o binário "docker-compose".
COMPOSE := $(shell docker compose version >/dev/null 2>&1 && echo "docker compose" || echo docker-compose)

.PHONY: bootstrap lint format test chat chat-falso api eval-local eval-falso db-up db-down

bootstrap:
	./scripts/bootstrap.sh

lint:
	$(UV) run ruff check .
	$(UV) run ruff format --check .

format:
	$(UV) run ruff format .
	$(UV) run ruff check --fix .

test:
	$(UV) run pytest -q

# Chat interativo no terminal com o modelo do .env. Use /sinais para ver o fluxo.
chat:
	$(UV) run python -m chat

# Mesmo chat forçando o modelo falso, sem Ollama (o .env continua obrigatório).
chat-falso:
	$(UV) run python -m chat --provedor falso

# Endpoints HTTP para um futuro front-end. Para testar manualmente: http://localhost:8000/docs
api:
	$(UV) run uvicorn api.app:criar_app --factory --reload --port 8000

# Golden set com o modelo do .env, fora do CI. Critério de pronto desta fase.
eval-local:
	$(UV) run python -m avaliacao

# Golden set forçando o modelo falso, sem Ollama (rápido, determinístico).
eval-falso:
	$(UV) run python -m avaliacao --provedor falso

db-up:
	$(COMPOSE) -f infra/docker-compose.yml --env-file .env up -d

db-down:
	$(COMPOSE) -f infra/docker-compose.yml --env-file .env down
