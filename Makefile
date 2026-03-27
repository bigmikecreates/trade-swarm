.PHONY: help install-deps install-dev install-postgres lock run batch mechanics list eval cleanup agents sources clean test

PYTHON := .venv/bin/python
PIP := .venv/bin/pip
CLI := $(PYTHON) lab/cli.py
LAB_DIR := lab
EXPERIMENTS_DIR := $(LAB_DIR)/experiments

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ─── Setup ─────────────────────────────────────────────────────────────────

install-deps: ## Install lab dependencies from lockfile
	$(PIP) install -r requirements.txt

install-dev: ## Install lab with dev dependencies
	$(PIP) install -r requirements.txt -e .

install-postgres: ## Install lab with PostgreSQL support
	$(PIP) install -r requirements.txt -e ".[postgres]"

lock: ## Regenerate requirements.lock from requirements.in
	$(PIP) pip-compile requirements.in --output-file=requirements.txt

venv: ## Create virtualenv and install dependencies
	python3 -m venv .venv
	$(PIP) install -r requirements.txt

# ─── Experiments ───────────────────────────────────────────────────────────────

run: ## Run a single experiment: make run AGENT=trend_signal SOURCE=synthetic
	$(CLI) run --agent $(AGENT) --source $(SOURCE) --symbol $(SYMBOL) --period $(PERIOD) --split $(SPLIT) --mode $(MODE)

batch: ## Run batch experiments: make batch AGENT=trend_signal SPLITS="70/30,75/25"
	$(CLI) batch --agent $(AGENT) --source $(SOURCE) --symbol $(SYMBOL) --period $(PERIOD) --splits $(SPLITS) --monte-carlo $(MONTE_CARLO)

mechanics: ## Run mechanics validation: make mechanics RUNS=500
	$(CLI) mechanics --runs $(RUNS) --config $(CONFIG)

list: ## List experiments: make list STRATEGY=trend_signal
	$(CLI) list --strategy $(STRATEGY) --limit $(LIMIT)

eval: ## Evaluate an experiment: make eval RUN=exp_001
	$(CLI) eval --run $(RUN)

agents: ## List available agents
	$(CLI) agents list

sources: ## List available data sources
	$(CLI) sources list

# ─── Cleanup ─────────────────────────────────────────────────────────────────

cleanup-dry: ## Preview directories to delete
	$(CLI) cleanup --dry-run --ttl $(TTL)

cleanup: ## Delete directories older than TTL days: make cleanup TTL=5
	$(CLI) cleanup --confirm --ttl $(TTL)

# ─── Dashboard ───────────────────────────────────────────────────────────────

dashboard: ## Run Flask dashboard
	$(PYTHON) $(LAB_DIR)/dashboard/app.py

# ─── Utilities ────────────────────────────────────────────────────────────────

test: ## Run a quick synthetic test
	$(CLI) run --agent trend_signal --source synthetic --init_cash 10000

clean: ## Remove all experiment directories
	rm -rf $(EXPERIMENTS_DIR)/*/
	@echo "Cleaned experiment directories"

clean-all: ## Remove all experiment directories + __pycache__
	rm -rf $(EXPERIMENTS_DIR)/*/
	find $(LAB_DIR) -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find $(LAB_DIR) -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "Cleaned everything"

.DEFAULT_GOAL := help
