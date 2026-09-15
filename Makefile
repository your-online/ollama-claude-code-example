.PHONY: test lint format check

test:
	python3 -m unittest discover -s tests -v

lint:
	uv run --group dev ruff check .
	uv run --group dev ruff format --check .

format:
	uv run --group dev ruff check --fix .
	uv run --group dev ruff format .

check: test lint
