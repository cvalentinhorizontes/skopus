.PHONY: install dev test lint typecheck fmt clean build

install:
	pip install -e .

dev:
	pip install -e ".[dev]"

test:
	pytest

lint:
	ruff check skopus tests

fmt:
	ruff format skopus tests

typecheck:
	mypy skopus

ci: lint typecheck test

clean:
	rm -rf build dist *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .pytest_cache -exec rm -rf {} +
	find . -type d -name .mypy_cache -exec rm -rf {} +
	find . -type d -name .ruff_cache -exec rm -rf {} +

build:
	python -m build
