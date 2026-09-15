# Repository Guidelines

## Architecture

This repository demonstrates the installed Claude Code harness against local Ollama.
Do not add a custom agent loop or API proxy. `local_demo/runtime.py` owns preflight
checks and process-scoped provider configuration; `cli.py` exposes explicit commands.
Only `chat` starts the harness. `setup` creates metadata from already downloaded
weights and must not pull models or perform inference.

`database.py` and `schema.sql` generate synthetic commerce data. Publication is atomic
and refuses to replace an existing database. The business seed is reproducible;
challenge values must remain cryptographically random and absent from retrieval
prompts. Generated files belong under ignored data/config/playground paths.

`audit.py` computes the Q1 answer from raw rows with integer arithmetic. Keep it
independent of candidate SQL. Refunds follow the original order date, including late
refunds; round discounted lines before summing. Equal totals use customer ID ordering.

## Commands and Style

- `uv sync --group dev` installs the pinned development tool.
- `make test` runs standard-library unittest without a model server.
- `make lint` checks Ruff lint rules and formatting.
- `make format` applies Ruff fixes and formatting.
- `make check` runs tests and lint together.
- `python3 -m unittest discover -s tests -v -k half_cent` runs the rounding case.

Use Python 3.10+ and standard-library runtime dependencies. Ruff enforces imports,
error checks and bugbear rules; formatting uses a 100-character target. See
`pyproject.toml` for the generator's long-line exception.

## Validation and Publication

Keep CI lightweight: mock API/subprocess boundaries and never load model weights.
Use small business-rule counterexamples alongside the seeded fixture. A matching
top-five result does not establish query correctness on all possible data.

Preserve manual tool permissions, local provider roles and non-destructive setup.
Do not add credentials, user paths, databases, session logs or generated playground
files to commits. Use the PR template to state behavior and verification. Document
model/context/hardware separately if a human explicitly runs an integration test;
never label a connected run as an offline proof.
