.PHONY: install test check run up down logs

install:
	uv sync --extra test

test:
	uv run pytest -q

check:
	uv run python -m compileall -q app tests
	uv run pytest -q

run:
	uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

up:
	podman compose up --build -d

down:
	podman compose down

logs:
	podman compose logs -f api
