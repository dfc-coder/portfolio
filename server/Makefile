.PHONY: install test check run up down logs models eval-ready eval eval-edge eval-view eval-legacy eval-legacy-strict eval-legacy-regression eval-legacy-smoke eval-legacy-holdout eval-legacy-stability tdd

ENGINE ?= $(shell if command -v podman >/dev/null 2>&1; then echo podman; elif command -v docker >/dev/null 2>&1; then echo docker; else echo none; fi)
COMPOSE = $(ENGINE) compose
EVAL_COMPOSE = $(COMPOSE) -f compose.yaml -f evals/compose.yaml
STABILITY_CASES = \
	--case general_hello \
	--case general_rest \
	--case portfolio_rust \
	--case portfolio_python \
	--case portfolio_fastapi \
	--case date_today \
	--case date_tomorrow \
	--case date_yesterday_weekday \
	--case date_known_weekday \
	--case date_one_week \
	--case date_two_hours \
	--case reminder_30m \
	--case reminder_2h \
	--case reminder_7d \
	--case mixed_greeting_portfolio \
	--case mixed_portfolio_and_date \
	--case mixed_switch_general \
	--case mixed_no_reminder \
	--case context_followup_go \
	--case context_reuse_date

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
	bash scripts/fetch_eval_models.sh runtime

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

# Official behavioral evaluation. Promptfoo runs outside app/ and talks to the real API.
eval: eval-ready
	$(EVAL_COMPOSE) run --rm promptfoo eval \
		-c promptfooconfig.yaml \
		--filter-pattern '^REG:' \
		--no-cache \
		--table

# Repeated probabilistic cases used to discover and reproduce edge behavior.
eval-edge: eval-ready
	$(EVAL_COMPOSE) run --rm promptfoo eval \
		-c promptfooconfig.yaml \
		--filter-pattern '^EDGE:' \
		--no-cache \
		--table

# Local result viewer. Open http://localhost:3000 after this command starts.
eval-view:
	$(EVAL_COMPOSE) run --rm --service-ports promptfoo view \
		/home/promptfoo/.promptfoo -n -p 3000

# Temporary legacy evaluator kept only while Promptfoo is calibrated against known cases.
eval-legacy: eval-ready
	uv run python tests/evals/run_agent_eval.py

eval-legacy-strict: eval-ready
	uv run python tests/evals/run_agent_eval.py --strict

eval-legacy-regression: eval-ready
	uv run python tests/evals/run_agent_eval.py \
		--case general_hello \
		--case general_joke \
		--case date_tomorrow \
		--case date_one_week \
		--results tests/evals/results/regression.json \
		--qwencloud tests/evals/results/regression-qwencloud.jsonl \
		--strict

eval-legacy-smoke: eval-ready
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

eval-legacy-holdout: eval-ready
	uv run python tests/evals/run_agent_eval.py \
		--cases tests/evals/agent_holdout.jsonl \
		--results tests/evals/results/holdout.json \
		--qwencloud tests/evals/results/holdout-qwencloud.jsonl \
		--strict

eval-legacy-stability: eval-ready
	@rm -f tests/evals/results/stability-*.json
	@for run in 1 2 3 4 5; do \
		echo "stability run $$run/5"; \
		uv run python tests/evals/run_agent_eval.py $(STABILITY_CASES) \
			--results tests/evals/results/stability-$$run.json \
			--qwencloud tests/evals/results/stability-$$run-qwencloud.jsonl || exit 1; \
	done
	@uv run python -c 'import glob,json,sys; files=glob.glob("tests/evals/results/stability-[1-5].json"); summaries=[json.load(open(p, encoding="utf-8"))["summary"] for p in files]; passed=sum(s["passed"] for s in summaries); total=sum(s["cases"] for s in summaries); rate=passed/total if total else 0; print(f"stability: {passed}/{total} ({rate:.1%})"); sys.exit(0 if total == 100 and rate >= 0.95 else 1)'

tdd:
	$(MAKE) install
	$(MAKE) check
	$(MAKE) models
	$(COMPOSE) up -d --build --force-recreate
	$(MAKE) eval
