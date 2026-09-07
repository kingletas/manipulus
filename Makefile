# Manipulus. Every verb is a make target, and `make help` lists them all.
#
# The Makefile holds no logic: each recipe delegates to uv, docker or the CLI itself.
# A target that needs an argument checks for it and prints usage rather than failing
# somewhere further in.

SHELL := /usr/bin/env bash
.SHELLFLAGS := -eu -o pipefail -c
.DEFAULT_GOAL := help

PREFIX  ?= $(HOME)/.local/bin
IMAGE   ?= manipulus:latest
ROOT    ?=
THEME   ?= frontend/Magento/luma
LOCALE  ?= en_US
PLAN    ?= manipulus.plan.json
MODULE  := dist/magento

.PHONY: help
help: ## Show this help
	@grep -hE '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| sort \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

# --- development ---

.PHONY: setup
setup: ## Create the virtualenv and install every dependency
	uv sync

.PHONY: check
check: lint private-info test ## Everything a commit has to pass (Python only; see `magento`)

.PHONY: private-info
private-info: ## Fail if anything tracked names the machine it was written on
	@scripts/check-no-private-info

.PHONY: check-all
check-all: check magento ## Everything, including the Magento module's own suite

.PHONY: lint
lint: ## Lint every source file
	uv run ruff check src tests

.PHONY: format
format: ## Rewrite every file in house style
	uv run ruff format src tests
	uv run ruff check --fix src tests

.PHONY: test
test: ## Run the test suite
	uv run pytest

# --- the Magento module ---

.PHONY: magento
magento: ## Run the Magento module's own checks. Needs its dev dependencies
	@if [[ ! -d $(MODULE)/vendor ]]; then \
		echo "  $(MODULE) has no dependencies installed."; \
		echo; \
		echo "      make magento-install     (needs repo.magento.com credentials)"; \
		echo; \
		exit 2; \
	fi
	@$(MAKE) --no-print-directory -C $(MODULE) check

.PHONY: magento-install
magento-install: ## Install the Magento module's dev dependencies
	@$(MAKE) --no-print-directory -C $(MODULE) install

# --- distribution ---

.PHONY: image
image: ## Build the container image
	docker build -t $(IMAGE) .

.PHONY: install
install: ## Put manipulus on your PATH
	@scripts/install $(PREFIX)

.PHONY: clean
clean: ## Remove build output and caches
	rm -rf .venv .ruff_cache .pytest_cache dist build src/*.egg-info
	find . -name __pycache__ -type d -prune -exec rm -rf {} +

# --- running it ---

.PHONY: graph
graph: ## Report the dependency graph. Needs ROOT=/path/to/magento
	@$(call need_root)
	uv run manipulus graph --root $(ROOT) --theme $(THEME) --locale $(LOCALE)

.PHONY: plan
plan: ## Decide the bundles. Needs ROOT=/path/to/magento
	@$(call need_root)
	uv run manipulus plan --root $(ROOT) --theme $(THEME) --locale $(LOCALE) --out $(PLAN)

.PHONY: bundles
bundles: ## Write the bundles from a plan. Needs ROOT=/path/to/magento
	@$(call need_root)
	uv run manipulus build --root $(ROOT) --theme $(THEME) --locale $(LOCALE) --plan $(PLAN)

define need_root
	if [[ -z "$(ROOT)" ]]; then \
		echo "This target needs a Magento root."; \
		echo; \
		echo "  make $@ ROOT=/path/to/magento"; \
		echo "  make $@ ROOT=/path/to/magento THEME=frontend/Vendor/theme LOCALE=en_US"; \
		echo; \
		exit 2; \
	fi
endef
