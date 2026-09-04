SHELL := /usr/bin/env bash
.DEFAULT_GOAL := help

ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
ENV_FILE ?= $(ROOT)/.env
ENV_EXAMPLE ?= $(ROOT)/.env.example
COMPOSE_FILE ?= $(ROOT)/compose.yaml
API_URL ?= http://localhost:8000
UV ?= uv
CRITICAL_REPETITIONS ?= 5
EVAL_GENERATED ?= tests/evals/generated/routing-candidates.jsonl
EVAL_RESPONSE_REPORT ?= tests/evals/reports/responses.json
EVAL_PORTFOLIO_PROMPT_DIR ?= tests/evals/reports/portfolio-prompts
PORTFOLIO_PROMPT_VERSION ?= v4
EVAL_BASELINE_REPORT ?=
EVAL_CANDIDATE_REPORT ?=

CONTAINER_ENGINE ?= $(shell if command -v podman >/dev/null 2>&1; then echo podman; elif command -v docker >/dev/null 2>&1; then echo docker; fi)
COMPOSE = $(CONTAINER_ENGINE) compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE)
HOST_UID := $(shell id -u)
HOST_GID := $(shell id -g)

ifeq ($(CONTAINER_ENGINE),podman)
EVAL_COMPOSE_RUN = PODMAN_USERNS=keep-id $(COMPOSE) run --rm --no-deps
else
EVAL_COMPOSE_RUN = $(COMPOSE) run --rm --no-deps --user "$(HOST_UID):$(HOST_GID)"
endif

.PHONY: help env env-check engine-check doctor config \
	up dev down stop restart reset build rebuild pull ps status \
	logs logs-api logs-llama logs-embedding shell-api \
	health ready wait-ready \
	compile test test-unit test-e2e check \
	eval-routing eval-scheduling eval-live eval-smoke eval-safety \
	eval-dataset-generate eval-dataset-validate eval-responses eval-portfolio-prompts eval-compare \
	eval-intents-challenge eval-intents-blind \
	eval-routes-v5 eval-routes-final clean model models

help: ## Show available targets
	@printf "\nPortfolio Business Representative\n\n"
	@awk 'BEGIN {FS = ":.*## "; printf "Usage: make <target>\n\nTargets:\n"} /^[a-zA-Z0-9_-]+:.*## / {printf "  %-24s %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@printf "\nOverrides: CONTAINER_ENGINE=podman|docker API_URL=http://... ENV_FILE=/path/.env CRITICAL_REPETITIONS=5 PORTFOLIO_PROMPT_VERSION=v1|v2|v3|v4\n\n"

env: ## Create .env from .env.example when missing
	@if [ -f "$(ENV_FILE)" ]; then \
		echo ".env already exists: $(ENV_FILE)"; \
	elif [ -f "$(ENV_EXAMPLE)" ]; then \
		cp "$(ENV_EXAMPLE)" "$(ENV_FILE)"; \
		echo "Created $(ENV_FILE). Review model, embedding and Calendar settings before starting."; \
	else \
		echo "Missing $(ENV_EXAMPLE)" >&2; \
		exit 1; \
	fi

engine-check: ## Verify Podman/Docker and Compose are available
	@if [ -z "$(CONTAINER_ENGINE)" ]; then \
		echo "Neither podman nor docker was found in PATH." >&2; \
		exit 1; \
	fi
	@$(CONTAINER_ENGINE) --version
	@$(CONTAINER_ENGINE) compose version >/dev/null

env-check: ## Validate .env and both configured GGUF files
	@if [ ! -f "$(ENV_FILE)" ]; then \
		echo "Missing $(ENV_FILE). Run: make env" >&2; \
		exit 1; \
	fi
	@set -a; source "$(ENV_FILE)"; set +a; \
	model_dir="$${LLAMA_MODELS_DIR:-./models}"; \
	if [[ "$$model_dir" != /* ]]; then model_dir="$(ROOT)/$$model_dir"; fi; \
	main_file="$${LLAMA_MODEL_FILE:-}"; \
	embedding_file="$${EMBEDDING_MODEL_FILE:-}"; \
	if [ -z "$$main_file" ] || [ ! -f "$$model_dir/$$main_file" ]; then \
		echo "Main GGUF not found: $$model_dir/$$main_file" >&2; exit 1; \
	fi; \
	if [ -z "$$embedding_file" ] || [ ! -f "$$model_dir/$$embedding_file" ]; then \
		echo "Embedding GGUF not found: $$model_dir/$$embedding_file" >&2; exit 1; \
	fi; \
	echo "Environment OK"; \
	echo "Main model: $$model_dir/$$main_file"; \
	echo "Embedding:  $$model_dir/$$embedding_file"

doctor: ## Diagnose runtime, env, models and service state
	@echo "== Runtime =="
	@if [ -n "$(CONTAINER_ENGINE)" ]; then $(CONTAINER_ENGINE) --version || true; $(CONTAINER_ENGINE) compose version || true; else echo "Container engine: NOT FOUND"; fi
	@echo; echo "== Python tooling =="
	@$(UV) --version 2>/dev/null || echo "uv: NOT FOUND"
	@echo; echo "== Environment =="
	@if [ -f "$(ENV_FILE)" ]; then echo ".env: $(ENV_FILE)"; $(MAKE) --no-print-directory env-check || true; else echo ".env: NOT FOUND (run: make env)"; fi
	@echo; echo "== Containers =="
	@if [ -n "$(CONTAINER_ENGINE)" ] && [ -f "$(ENV_FILE)" ]; then $(COMPOSE) ps || true; else echo "Skipped"; fi
	@echo; echo "== API =="
	@curl -fsS "$(API_URL)/ready" 2>/dev/null || echo "API not ready at $(API_URL)"
	@echo

config: engine-check env-check ## Render resolved Compose configuration
	@cd "$(ROOT)" && $(COMPOSE) config

up: engine-check env-check ## Start API + main LLM + embedding service in background
	@cd "$(ROOT)" && $(COMPOSE) up -d
	@$(MAKE) --no-print-directory wait-ready

dev: engine-check env-check ## Start all services in foreground with build
	@cd "$(ROOT)" && $(COMPOSE) up --build

down: engine-check ## Stop and remove project containers
	@if [ -f "$(ENV_FILE)" ]; then cd "$(ROOT)" && $(COMPOSE) down; else echo "Nothing to stop: $(ENV_FILE) is missing."; fi

stop: down ## Alias for down

restart: engine-check env-check ## Restart running services
	@cd "$(ROOT)" && $(COMPOSE) restart
	@$(MAKE) --no-print-directory wait-ready

reset: engine-check env-check ## Recreate services using current images/config
	@cd "$(ROOT)" && $(COMPOSE) down
	@cd "$(ROOT)" && $(COMPOSE) up -d --build --force-recreate
	@$(MAKE) --no-print-directory wait-ready

build: engine-check env-check ## Build the local API image
	@cd "$(ROOT)" && $(COMPOSE) build api

rebuild: engine-check env-check ## Rebuild API without build cache
	@cd "$(ROOT)" && $(COMPOSE) build --no-cache api

pull: engine-check env-check ## Pull llama.cpp image used by both model services
	@cd "$(ROOT)" && $(COMPOSE) pull llama embedding

ps: engine-check env-check ## Show service/container status
	@cd "$(ROOT)" && $(COMPOSE) ps

status: ps ## Alias for ps

logs: engine-check env-check ## Follow logs from all services
	@cd "$(ROOT)" && $(COMPOSE) logs -f --tail=200

logs-api: engine-check env-check ## Follow FastAPI logs
	@cd "$(ROOT)" && $(COMPOSE) logs -f --tail=200 api

logs-llama: engine-check env-check ## Follow main Qwen logs
	@cd "$(ROOT)" && $(COMPOSE) logs -f --tail=200 llama

logs-embedding: engine-check env-check ## Follow semantic embedding service logs
	@cd "$(ROOT)" && $(COMPOSE) logs -f --tail=200 embedding

shell-api: engine-check env-check ## Open a shell inside the API container
	@cd "$(ROOT)" && $(COMPOSE) exec api sh

health: ## Query FastAPI health endpoint
	@curl -fsS "$(API_URL)/health"; echo

ready: ## Query main LLM + embedding readiness
	@curl -fsS "$(API_URL)/ready"; echo

wait-ready: ## Wait until both models are ready through FastAPI
	@echo "Waiting for $(API_URL)/ready ..."
	@for attempt in $$(seq 1 60); do \
		body="$$(curl -fsS "$(API_URL)/ready" 2>/dev/null || true)"; \
		if echo "$$body" | grep -q '"status":"ok"' && echo "$$body" | grep -q '"llama":"ready"' && echo "$$body" | grep -q '"embedding":"ready"'; then \
			echo "Ready: $$body"; exit 0; \
		fi; \
		printf "."; sleep 2; \
	done; \
	echo; echo "Timed out waiting for the API. Try: make logs" >&2; exit 1

compile: ## Compile Python sources and tests
	@cd "$(ROOT)" && $(UV) run python -m compileall -q app tests

test: ## Run the complete pytest suite with test extras installed
	@cd "$(ROOT)" && PYTHONPATH=. $(UV) run --extra test pytest -q

test-unit: ## Run fast unit tests only with test extras installed
	@cd "$(ROOT)" && PYTHONPATH=. $(UV) run --extra test pytest -q tests/unit

test-e2e: ## Run end-to-end agent tests with test extras installed
	@cd "$(ROOT)" && PYTHONPATH=. $(UV) run --extra test pytest -q tests/e2e

check: compile test ## Run compile + complete test suite

eval-dataset-validate: ## Validate canonical eval splits and optional generated candidate
	@cd "$(ROOT)" && PYTHONPATH=. $(UV) run --extra test python tests/evals/datasets/validate.py --generated "$(EVAL_GENERATED)"

eval-dataset-generate: up ## Generate routing dataset candidates; never mutates canonical splits
	@cd "$(ROOT)" && mkdir -p "$$(dirname "$(EVAL_GENERATED)")"
	@cd "$(ROOT)" && $(EVAL_COMPOSE_RUN) \
		-v "$(ROOT):/workspace:Z" -w /workspace -e PYTHONPATH=/workspace \
		api python tests/evals/datasets/generate.py \
		--spec tests/evals/datasets/specs/routing.json \
		--output "$(EVAL_GENERATED)"
	@$(MAKE) --no-print-directory eval-dataset-validate

eval-responses: up ## Evaluate response prompts; portfolio defaults to v4 and can be overridden
	@cd "$(ROOT)" && mkdir -p "$$(dirname "$(EVAL_RESPONSE_REPORT)")"
	@cd "$(ROOT)" && $(EVAL_COMPOSE_RUN) \
		-v "$(ROOT):/workspace:Z" -w /workspace -e PYTHONPATH=/workspace \
		api python tests/evals/run_response_eval.py \
		--cases tests/evals/responses/cases.jsonl \
		--portfolio-prompt-version "$(PORTFOLIO_PROMPT_VERSION)" \
		--output "$(EVAL_RESPONSE_REPORT)" --strict

eval-portfolio-prompts: up ## Run portfolio-v1 -> v4 on the same portfolio cases and compare every step
	@cd "$(ROOT)" && mkdir -p "$(EVAL_PORTFOLIO_PROMPT_DIR)"
	@cd "$(ROOT)" && $(EVAL_COMPOSE_RUN) \
		-v "$(ROOT):/workspace:Z" -w /workspace -e PYTHONPATH=/workspace \
		api python tests/evals/run_portfolio_prompt_ladder.py \
		--cases tests/evals/responses/cases.jsonl \
		--output-dir "$(EVAL_PORTFOLIO_PROMPT_DIR)" --strict

eval-compare: ## Compare shared numeric metrics in two saved evaluation reports
	@if [ -z "$(EVAL_BASELINE_REPORT)" ] || [ -z "$(EVAL_CANDIDATE_REPORT)" ]; then \
		echo "Set EVAL_BASELINE_REPORT and EVAL_CANDIDATE_REPORT." >&2; exit 1; \
	fi
	@cd "$(ROOT)" && PYTHONPATH=. $(UV) run --extra test python tests/evals/compare_reports.py \
		--baseline "$(EVAL_BASELINE_REPORT)" --candidate "$(EVAL_CANDIDATE_REPORT)"

eval-safety: test-e2e ## Run deterministic E2E safety and side-effect contracts

eval-intents-challenge: engine-check env-check ## Historical v4 training/challenge pipeline; keep only for comparison
	@cd "$(ROOT)" && bash tests/evals/run_intent_pipeline.sh

eval-intents-blind: engine-check env-check ## Historical v4 blind gate; already consumed, do not use as a final gate
	@cd "$(ROOT)" && bash tests/evals/run_intent_pipeline.sh --blind

eval-routes-v5: engine-check env-check ## Train nonlinear 4-class candidate and require challenge + historical blind regression
	@cd "$(ROOT)" && bash tests/evals/run_nonlinear_route_pipeline.sh

eval-routes-final: engine-check env-check ## Evaluate frozen nonlinear artifact once on final_holdout_v2 without retraining
	@cd "$(ROOT)" && bash tests/evals/run_nonlinear_route_final.sh

eval-routing: up ## Run the complete live embedding routing/conversation evaluation
	@echo "Full routing/conversation eval: all cases run; CRITICAL_REPETITIONS only changes repeated critical cases."
	@cd "$(ROOT)" && $(EVAL_COMPOSE_RUN) \
		-v "$(ROOT):/workspace:Z" -w /workspace -e PYTHONPATH=/workspace \
		api python tests/evals/run_live.py --critical-repetitions $(CRITICAL_REPETITIONS)

eval-scheduling: up ## Run the complete SchedulingTurn structured semantic evaluation
	@echo "Full scheduling eval: all SchedulingTurn cases run; CRITICAL_REPETITIONS only changes repeated critical cases."
	@cd "$(ROOT)" && $(EVAL_COMPOSE_RUN) \
		-v "$(ROOT):/workspace:Z" -w /workspace -e PYTHONPATH=/workspace \
		api python tests/evals/run_scheduling_turn_live.py --critical-repetitions $(CRITICAL_REPETITIONS)

eval-live: eval-routing eval-scheduling ## Run all complete live-model evaluations

eval-smoke: up ## Run a small live-model regression sample with visible per-case progress
	@echo "Running fast live-model smoke evaluation with per-case progress."
	@cd "$(ROOT)" && $(EVAL_COMPOSE_RUN) \
		-v "$(ROOT):/workspace:Z" -w /workspace -e PYTHONPATH=/workspace \
		api python -u tests/evals/run_smoke.py

clean: ## Remove Python/test caches only; keeps models and containers
	@find "$(ROOT)" -type d -name __pycache__ -prune -exec rm -rf {} +
	@rm -rf "$(ROOT)/.pytest_cache"
	@echo "Caches removed."

models: env-check ## Show both configured GGUF paths and sizes
	@set -a; source "$(ENV_FILE)"; set +a; \
	model_dir="$${LLAMA_MODELS_DIR:-./models}"; \
	if [[ "$$model_dir" != /* ]]; then model_dir="$(ROOT)/$$model_dir"; fi; \
	du -h "$$model_dir/$$LLAMA_MODEL_FILE" "$$model_dir/$$EMBEDDING_MODEL_FILE"

model: models ## Alias for models
