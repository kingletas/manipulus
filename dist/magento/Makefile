# Manipulus_Bundles
#
# Run `make` with no arguments for the list.
#
# The suite needs the Magento classes. `make install` resolves them itself and
# needs repo.magento.com credentials; without those, point M2_VENDOR at an
# existing installation's vendor directory and the bootstrap borrows it.

SHELL       := /usr/bin/env bash
.SHELLFLAGS := -eu -o pipefail -c
.DEFAULT_GOAL := help

# Empty by default: `composer install` here resolves the framework itself, and
# the bootstrap prefers that. Set this only to borrow another installation's
# vendor tree instead -- see Test/bootstrap.php.
M2_VENDOR ?=
COMPOSER  ?= composer
PHP       ?= php

.PHONY: help
help: ## Show this help
	@echo
	@echo "  Manipulus_Bundles"
	@echo
	@grep -hE '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "    \033[36m%-12s\033[0m %s\n", $$1, $$2}'
	@echo

.PHONY: install
install: ## Install dev dependencies (needs repo.magento.com credentials)
	@$(COMPOSER) install

.PHONY: check
check: lint cs test ## Everything a commit has to pass

.PHONY: lint
lint: ## Parse every PHP file with the real interpreter
	@find . -path ./vendor -prune -o -name '*.php' -print0 | xargs -0 -n1 $(PHP) -l > /dev/null
	@echo "  every PHP file parses"

.PHONY: cs
cs: ## Magento's coding standard
	@vendor/bin/phpcs --standard=phpcs.xml.dist

.PHONY: cs-fix
cs-fix: ## Fix what the coding standard can fix
	@vendor/bin/phpcbf --standard=phpcs.xml.dist

.PHONY: stan
stan: ## Static analysis
	@vendor/bin/phpstan analyse --configuration phpstan.neon.dist --no-progress

.PHONY: test
test: ## The unit suite
	@M2_VENDOR="$(M2_VENDOR)" vendor/bin/phpunit --configuration phpunit.xml.dist

.PHONY: clean
clean: ## Remove installed dependencies and caches
	rm -rf vendor .phpunit.cache
