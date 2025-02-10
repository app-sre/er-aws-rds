CONTAINER_ENGINE ?= $(shell which podman >/dev/null 2>&1 && echo podman || echo docker)

.PHONY: format
format:
	uv run ruff check
	uv run ruff format

.PHONY: image_tests
image_tests:
	# test /tmp must be empty
	[ -z "$(shell ls -A /tmp)" ]
	# validate_plan.py must exist
	[ -f "hooks/validate_plan.py" ]

.PHONY: code_tests
code_tests:
	uv run ruff check --no-fix
	uv run ruff format --check
	uv run mypy
	uv run pytest -vv --cov=er_aws_rds --cov-report=term-missing --cov-report xml

.PHONY: dependency_tests
dependency_tests:
	python -c "import cdktf_cdktf_provider_random"
	python -c "import cdktf_cdktf_provider_aws"

in_container_test: image_tests code_tests dependency_tests

.PHONY: test
test:
	$(CONTAINER_ENGINE) build --progress plain --target test -t er-aws-rds:test .

.PHONY: build
build:
	$(CONTAINER_ENGINE) build --progress plain --target prod -t er-aws-rds:prod .

.PHONY: dev
dev:
	uv sync
