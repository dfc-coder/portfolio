.PHONY: install test check run up down logs eval eval-strict eval-smoke

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

eval:
	uv run python tests/evals/run_agent_eval.py

eval-strict:
	uv run python tests/evals/run_agent_eval.py --strict

eval-smoke:
	uv run python tests/evals/run_agent_eval.py \
		--case general_hello \
		--case general_joke \
		--case date_tomorrow \
		--case date_yesterday_weekday \
		--case date_known_weekday \
		--case date_one_week \
		--case date_known_past \
		--case reminder_30m \
		--case reminder_2h \
		--case reminder_7d \
		--results tests/evals/results/smoke.json \
		--qwencloud tests/evals/results/smoke-qwencloud.jsonl \
		--strict
