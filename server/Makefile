.PHONY: install test run up down logs models eval-ready eval eval-edge eval-view verify

ENGINE ?= $(shell if command -v podman >/dev/null 2>&1; then echo podman; elif command -v docker >/dev/null 2>&1; then echo docker; else echo none; fi)
COMPOSE = $(ENGINE) compose
EVAL_COMPOSE = $(COMPOSE) -f compose.yaml -f evals/compose.yaml

install:
	uv sync --extra test

test:
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
	bash scripts/fetch_models.sh

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

eval: eval-ready
	$(EVAL_COMPOSE) run --rm promptfoo eval \
		-c promptfooconfig.yaml \
		--filter-pattern '^REG:' \
		--no-cache \
		--table

eval-edge: eval-ready
	$(EVAL_COMPOSE) run --rm promptfoo eval \
		-c promptfooconfig.yaml \
		--filter-pattern '^EDGE:' \
		--no-cache \
		--table

eval-view:
	$(EVAL_COMPOSE) run --rm --service-ports promptfoo view \
		/home/promptfoo/.promptfoo -n -p 3000

verify: test models
	$(COMPOSE) up -d --build --force-recreate
	$(MAKE) eval
