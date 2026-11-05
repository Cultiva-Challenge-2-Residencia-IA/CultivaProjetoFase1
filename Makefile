.PHONY: setup up down ingest ask serve test eval lint

setup:
	python3 -m venv .venv
	. .venv/bin/activate && pip install --upgrade pip && pip install -r requirements.txt

up:
	docker compose up -d

down:
	docker compose down

ingest:
	python -m src.rag.ingest

ask:
	python -m src.cli ask "$(QUESTION)"

serve:
	uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000

test:
	pytest -q

eval:
	python -m eval.run

lint:
	ruff check .
