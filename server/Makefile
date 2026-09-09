.PHONY: install test check run up down logs models reranker-model eval-ready eval-reranker-ready eval-tools-strict eval eval-strict eval-smoke tdd

ENGINE ?= $(shell if command -v podman >/dev/null 2>&1; then echo podman; elif command -v docker >/dev/null 2>&1; then echo docker; else echo none; fi)
COMPOSE = $(ENGINE) compose

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
	$(COMPOSE) up --build -d

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f api

models:
	bash scripts/fetch_eval_models.sh all

reranker-model:
	bash scripts/fetch_eval_models.sh reranker

eval-ready:
	@echo "Waiting for portfolio API on http://localhost:8000/health..."
	@for i in $$(seq 1 90); do \
		if curl -fsS http://localhost:8000/health >/dev/null 2>&1; then \
			echo "Portfolio API ready"; \
			exit 0; \
		fi; \
		sleep 1; \
	done; \
	echo "Portfolio API did not become ready within 90s" >&2; \
	exit 1

eval-reranker-ready:
	@echo "Waiting for reranker on http://localhost:8082/health..."
	@for i in $$(seq 1 90); do \
		if curl -fsS http://localhost:8082/health >/dev/null 2>&1; then \
			echo "Reranker ready"; \
			exit 0; \
		fi; \
		sleep 1; \
	done; \
	echo "Reranker did not become ready within 90s" >&2; \
	exit 1

eval-tools-strict: eval-reranker-ready
	uv run python tests/evals/run_tool_search_eval.py --strict

eval: eval-ready
	uv run python tests/evals/run_agent_eval.py

eval-strict: eval-ready
	uv run python tests/evals/run_agent_eval.py --strict

eval-smoke: eval-ready
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

tdd:
	$(MAKE) install
	$(MAKE) check
	$(MAKE) reranker-model
	$(COMPOSE) up -d --force-recreate reranker
	$(MAKE) eval-tools-strict
	$(MAKE) models
	$(COMPOSE) up -d --build --force-recreate
	$(MAKE) eval-strict
