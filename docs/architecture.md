# Architecture and data rules

## Separation of responsibilities

- `runtime.py` checks local dependencies and model metadata, creates an Ollama alias,
  and launches the installed Claude Code binary with process-scoped settings. It does
  not implement a model loop, execute tool requests or proxy the Anthropic API.
- `database.py` creates a seeded synthetic SQLite fixture. A temporary database is
  fully populated before atomic, no-clobber publication. Existing files are preserved.
- `audit.py` computes the Q1 answer from raw rows, independently of model-written SQL.
  Candidate queries run in a read-only connection with an authorizer, a time budget
  and a bounded result. This is a demo verifier, not a hostile-code isolation service.
- `cli.py` binds the explicit commands together. `init`, `challenge`, `check-code`
  and `verify-query` never need a model server. `setup` and `check` contact only the
  local Ollama server without performing inference. Only `chat` launches the harness.

No runtime third-party Python dependencies are required. Generated database files,
Claude configuration, sessions and playground work are ignored by Git.

## Revenue definition

For each line, use integer EUR cents and round half up:

```text
line revenue = ROUND(quantity × unit_price_cents × (10000 - discount_bps) / 10000)
net revenue  = sum(line revenue) - sum(refund_cents)
```

The SQL version must use `/ 10000.0` to prevent SQLite integer division. The oracle
uses `(numerator + 5000) // 10000` for the nonnegative fixture values; it does not
reuse the candidate SQL or floating-point arithmetic.

Q1 2026 includes completed orders on or after January 1 and before April 1. Refunds
are attributed to their original order, even when `returned_at` is outside Q1.
Payments represent cash received and are not used to calculate revenue. Regions
come from the customer record. Break equal net totals by customer ID ascending.

Orders have multiple items and may have multiple payments, shipments and returns.
Aggregate each relationship before joining, rather than multiplying raw child rows.

## Model configuration

The public example defaults to `gpt-oss:20b`, aliased with a 16k context limit and
4,096 output tokens. Claude Code's known model roles point to that alias. The
launcher uses `--bare`, an isolated config directory, explicit built-in tools and
manual permissions. It disables known nonessential traffic and proxying of loopback
checks. This reduces external integrations; it does not enforce an OS network sandbox.

The startup check refuses other already loaded models. It is a preflight check,
not a global concurrency lock: do not launch multiple model sessions yourself.
16k is intentionally conservative for a small playground; larger projects may need
more context and memory. Ollama's general guidance recommends 64k+ for larger repos.
