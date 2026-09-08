.PHONY: install format lint typecheck test check prepare-data train api docker

install:
	uv sync --all-extras

format:
	uv run ruff format .
	uv run ruff check --fix .

lint:
	uv run ruff check .
	uv run ruff format --check .

typecheck:
	uv run mypy

test:
	uv run pytest --cov=src/variantrank --cov-report=term-missing

check: lint typecheck test

prepare-data:
	uv run variantrank prepare-data

train:
	uv run variantrank train --strategy both

api:
	uv run uvicorn variantrank.api.app:app --reload

docker:
	docker build -t variantrank:dev .
