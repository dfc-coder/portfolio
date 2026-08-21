SHELL := /usr/bin/env bash
.DEFAULT_GOAL := help

ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
ENV_FILE ?= $(ROOT)/.env
ENV_EXAMPLE ?= $(ROOT)/.env.example
COMPOSE_FILE ?= $(ROOT)/compose.yaml
API_URL ?= http://localhost:8000
UV ?= uv

CONTAINER_ENGINE ?= $(shell if command -v podman >/dev/null 2>&1; then echo podman; elif command -v docker >/dev/null 2>&1; then echo docker; fi)
COMPOSE = $(CONTAINER_ENGINE) compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE)

.PHONY: help env env-check engine-check doctor config \
	up dev down stop restart reset build rebuild pull ps status \
	logs logs-api logs-llama shell-api \
	health ready wait-ready \
	compile test test-unit test-e2e check clean model

help: ## Show available targets
	@printf "\nPortfolio Business Representative\n\n"
	@awk 'BEGIN {FS = ":.*## "; printf "Usage: make <target>\n\nTargets:\n"} /^[a-zA-Z0-9_-]+:.*## / {printf "  %-16s %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@printf "\nOverrides: CONTAINER_ENGINE=podman|docker API_URL=http://... ENV_FILE=/path/.env\n\n"

env: ## Create .env from .env.example when missing
	@if [ -f "$(ENV_FILE)" ]; then \
		echo ".env already exists: $(ENV_FILE)"; \
	elif [ -f "$(ENV_EXAMPLE)" ]; then \
		cp "$(ENV_EXAMPLE)" "$(ENV_FILE)"; \
		echo "Created $(ENV_FILE). Review model and Calendar settings before starting."; \
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

env-check: ## Validate .env and configured GGUF path
	@if [ ! -f "$(ENV_FILE)" ]; then \
		echo "Missing $(ENV_FILE). Run: make env" >&2; \
		exit 1; \
	fi
	@set -a; source "$(ENV_FILE)"; set +a; \
	model_dir="$${LLAMA_MODELS_DIR:-./models}"; \
	model_file="$${LLAMA_MODEL_FILE:-}"; \
	if [ -z "$$model_file" ]; then \
		echo "LLAMA_MODEL_FILE is not configured in $(ENV_FILE)" >&2; \
		exit 1; \
	fi; \
	if [[ "$$model_dir" != /* ]]; then model_dir="$(ROOT)/$$model_dir"; fi; \
	if [ ! -f "$$model_dir/$$model_file" ]; then \
		echo "GGUF not found: $$model_dir/$$model_file" >&2; \
		exit 1; \
	fi; \
	echo "Environment OK"; \
	echo "Model: $$model_dir/$$model_file"

doctor: ## Diagnose local runtime, env, model and service state
	@echo "== Runtime =="
	@if [ -n "$(CONTAINER_ENGINE)" ]; then \
		$(CONTAINER_ENGINE) --version || true; \
		$(CONTAINER_ENGINE) compose version || true; \
	else \
		echo "Container engine: NOT FOUND"; \
	fi
	@echo
	@echo "== Python tooling =="
	@$(UV) --version 2>/dev/null || echo "uv: NOT FOUND"
	@echo
	@echo "== Environment =="
	@if [ -f "$(ENV_FILE)" ]; then \
		echo ".env: $(ENV_FILE)"; \
		$(MAKE) --no-print-directory env-check || true; \
	else \
		echo ".env: NOT FOUND (run: make env)"; \
	fi
	@echo
	@echo "== Containers =="
	@if [ -n "$(CONTAINER_ENGINE)" ] && [ -f "$(ENV_FILE)" ]; then \
		$(COMPOSE) ps || true; \
	else \
		echo "Skipped"; \
	fi
	@echo
	@echo "== API =="
	@curl -fsS "$(API_URL)/ready" 2>/dev/null || echo "API not ready at $(API_URL)"
	@echo

config: engine-check env-check ## Render resolved Compose configuration
	@cd "$(ROOT)" && $(COMPOSE) config

up: engine-check env-check ## Start API + llama.cpp in background
	@cd "$(ROOT)" && $(COMPOSE) up -d
	@$(MAKE) --no-print-directory wait-ready

dev: engine-check env-check ## Start API + llama.cpp in foreground with build
	@cd "$(ROOT)" && $(COMPOSE) up --build

down: engine-check ## Stop and remove project containers
	@if [ -f "$(ENV_FILE)" ]; then cd "$(ROOT)" && $(COMPOSE) down; else echo "Nothing to stop: $(ENV_FILE) is missing."; fi

stop: down ## Alias for down

restart: engine-check env-check ## Restart running services
	@cd "$(ROOT)" && $(COMPOSE) restart
	@$(MAKE) --no-print-directory wait-ready

reset: engine-check env-check ## Recreate services using the current images/config
	@cd "$(ROOT)" && $(COMPOSE) down
	@cd "$(ROOT)" && $(COMPOSE) up -d --build --force-recreate
	@$(MAKE) --no-print-directory wait-ready

build: engine-check env-check ## Build the local API image
	@cd "$(ROOT)" && $(COMPOSE) build api

rebuild: engine-check env-check ## Rebuild API without build cache
	@cd "$(ROOT)" && $(COMPOSE) build --no-cache api

pull: engine-check env-check ## Pull the configured llama.cpp image
	@cd "$(ROOT)" && $(COMPOSE) pull llama

ps: engine-check env-check ## Show service/container status
	@cd "$(ROOT)" && $(COMPOSE) ps

status: ps ## Alias for ps

logs: engine-check env-check ## Follow logs from all services
	@cd "$(ROOT)" && $(COMPOSE) logs -f --tail=200

logs-api: engine-check env-check ## Follow FastAPI logs
	@cd "$(ROOT)" && $(COMPOSE) logs -f --tail=200 api

logs-llama: engine-check env-check ## Follow llama.cpp logs
	@cd "$(ROOT)" && $(COMPOSE) logs -f --tail=200 llama

shell-api: engine-check env-check ## Open a shell inside the API container
	@cd "$(ROOT)" && $(COMPOSE) exec api sh

health: ## Query FastAPI health endpoint
	@curl -fsS "$(API_URL)/health"; echo

ready: ## Query FastAPI readiness / llama.cpp state
	@curl -fsS "$(API_URL)/ready"; echo

wait-ready: ## Wait until FastAPI reports llama.cpp ready
	@echo "Waiting for $(API_URL)/ready ..."
	@for attempt in $$(seq 1 45); do \
		body="$$(curl -fsS "$(API_URL)/ready" 2>/dev/null || true)"; \
		if echo "$$body" | grep -q '"status":"ok"' && echo "$$body" | grep -q '"llama":"ready"'; then \
			echo "Ready: $$body"; \
			exit 0; \
		fi; \
		printf "."; \
		sleep 2; \
	done; \
	echo; \
	echo "Timed out waiting for the API. Try: make logs" >&2; \
	exit 1

compile: ## Compile Python sources and tests
	@cd "$(ROOT)" && $(UV) run python -m compileall -q app tests

test: ## Run the complete pytest suite
	@cd "$(ROOT)" && PYTHONPATH=. $(UV) run pytest -q

test-unit: ## Run fast unit tests only
	@cd "$(ROOT)" && PYTHONPATH=. $(UV) run pytest -q tests/unit

test-e2e: ## Run end-to-end agent tests
	@cd "$(ROOT)" && PYTHONPATH=. $(UV) run pytest -q tests/e2e

check: compile test ## Run compile + complete test suite

clean: ## Remove Python/test caches only; keeps models and containers
	@find "$(ROOT)" -type d -name __pycache__ -prune -exec rm -rf {} +
	@rm -rf "$(ROOT)/.pytest_cache"
	@echo "Caches removed."

model: env-check ## Show configured GGUF path and size
	@set -a; source "$(ENV_FILE)"; set +a; \
	model_dir="$${LLAMA_MODELS_DIR:-./models}"; \
	if [[ "$$model_dir" != /* ]]; then model_dir="$(ROOT)/$$model_dir"; fi; \
	model_path="$$model_dir/$$LLAMA_MODEL_FILE"; \
	echo "$$model_path"; \
	du -h "$$model_path"
