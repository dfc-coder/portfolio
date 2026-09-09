.PHONY: install test check run up down logs reranker-model eval-ready eval-reranker-ready eval-tools-strict eval eval-strict eval-smoke tdd

RERANKER_MODEL_URL ?= https://huggingface.co/ggml-org/Qwen3-Reranker-0.6B-Q8_0-GGUF/resolve/main/qwen3-reranker-0.6b-q8_0.gguf?download=true
RERANKER_MODEL_SHA256 ?= 22c9979ce4fbcdc5acdc310c6641c32797eff1aa980b8f7a2db8a8ea23429a48

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

reranker-model:
	@models_dir=$$(sed -n 's/^LLAMA_MODELS_DIR=//p' .env 2>/dev/null | tail -n 1); \
	models_dir=$${models_dir:-./models}; \
	model_file=$$(sed -n 's/^RERANKER_MODEL_FILE=//p' .env 2>/dev/null | tail -n 1); \
	model_file=$${model_file:-qwen3-reranker-0.6b-q8_0.gguf}; \
	path="$$models_dir/$$model_file"; \
	mkdir -p "$$models_dir"; \
	if [ ! -f "$$path" ]; then \
		echo "Downloading Qwen3-Reranker-0.6B Q8_0 to $$path..."; \
		curl -fL "$(RERANKER_MODEL_URL)" -o "$$path.part"; \
		mv "$$path.part" "$$path"; \
	fi; \
	if [ "$$model_file" = "qwen3-reranker-0.6b-q8_0.gguf" ]; then \
		echo "$(RERANKER_MODEL_SHA256)  $$path" | sha256sum -c -; \
	fi

eval-ready:
	@echo "Waiting for portfolio API on http://localhost:8000/health..."
	@for i in $$(seq 1 60); do \
		if curl -fsS http://localhost:8000/health >/dev/null 2>&1; then \
			echo "Portfolio API ready"; \
			exit 0; \
		fi; \
		sleep 1; \
	done; \
	echo "Portfolio API did not become ready within 60s" >&2; \
	exit 1

eval-reranker-ready:
	@echo "Waiting for reranker on http://localhost:8082/health..."
	@for i in $$(seq 1 60); do \
		if curl -fsS http://localhost:8082/health >/dev/null 2>&1; then \
			echo "Reranker ready"; \
			exit 0; \
		fi; \
		sleep 1; \
	done; \
	echo "Reranker did not become ready within 60s" >&2; \
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
	$(MAKE) check
	$(MAKE) reranker-model
	podman compose up -d --build --force-recreate
	$(MAKE) eval-tools-strict
	$(MAKE) eval-strict
