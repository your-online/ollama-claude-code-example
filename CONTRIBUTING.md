# Contributing

Use Python 3.10+ and run from the repository root. Runtime code must keep working
without third-party Python packages. `uv sync --group dev` installs the pinned Ruff
development tool; `make test` uses standard-library unittest.

Before submitting a pull request, run `make check`. CI covers Python 3.10, 3.12 and
3.14. For an individual case:

```bash
python3 -m unittest discover -s tests -v -k half_cent
```

Keep model execution opt-in. Do not add inference, model downloads or GPU requirements
to tests or CI. Mock the local API and subprocess boundary. Business-rule tests
should use small counterexamples in addition to the generated fixture.

Keep `init` non-destructive, credentials process-scoped and the normal Claude Code
permission flow enabled. Do not add a cloud fallback to this local example.

Describe the resulting behavior and validation in the PR template. Include exact
model, context and hardware details if you choose to perform an integration test.
Do not publish generated databases, nonces, session logs, private paths or credentials.
New setup/runtime behavior must also update the README and architecture notes.
