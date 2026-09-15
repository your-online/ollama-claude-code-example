# Validation record

## Evidence from the original experiment

The original macOS session used Ollama 0.34.0 and Claude Code 2.1.272 with local
`gpt-oss:20b`. The real harness invoked Bash, executed a read-only SQLite command
and returned a newly generated random value correctly.

A separate top-five net-revenue answer was audited by replaying its SQL and by an
independent integer-cent Python calculation. All 146 customer totals for that
original fixture agreed, covering 307 completed Q1 orders and 1,058 order lines.
Late refunds, discounts, order status and ranking were explicitly checked.

Those figures describe the private original fixture, **not this newly seeded public
fixture**. No original database, transcript, user path, model session, nonce or answer
log is included in the repository.

## Packaging checks

The test suite verifies fixture integrity, reproducibility, non-replacement of
existing data, unpredictable challenge values, half-cent rounding, late refunds,
cancelled orders, rejection of incorrect result queries, read-only query enforcement,
local-provider configuration and rejection of other loaded models. Network/model
interactions are mocked; CI never downloads weights or starts inference.

The public refactor is covered by these lightweight checks. A new full model run
was deliberately not performed during packaging after the original machine became
unresponsive under memory pressure. The 16k configuration reduces context allocation
but does not guarantee sufficient RAM or a correct answer on every task.

## Scope of a successful audit

`verify-query` compares exactly five ordered results against the current database.
It verifies the output, not the reasoning trace, provenance of every tool call or
correctness on unseen fixtures. A wrong query can coincidentally return the correct
top five if affected customers rank lower. Read the query and use purpose-built
counterexamples when general correctness matters.

The offline walkthrough has not been executed by CI. A fresh-code match alone is
not proof that the operating system had no internet connection.
