# Claude Code + Ollama, entirely local inference

[![Checks](https://github.com/your-online/ollama-claude-code-example/actions/workflows/ci.yml/badge.svg)](https://github.com/your-online/ollama-claude-code-example/actions/workflows/ci.yml)

Use the **real Claude Code CLI** with a local Ollama model. Let it run Bash, inspect a
SQLite database, write SQL and edit files. Then independently check whether its answer
is right.

This is a small educational example, not a replacement agent framework. There is no
custom chat loop, API proxy, LangChain dependency or database server.

```text
Your question → Claude Code CLI → Ollama on 127.0.0.1:11434 → local model
                       ↓ native Bash tool
                 sqlite3 -readonly → generated dummy database
                       ↓
                 query result → model → answer
```

## Before you start

- macOS or Linux; Windows users can use WSL2 with Ollama and Claude Code **inside the
  same environment**. Native Windows and cross-host WSL routing are not covered.
- Python **3.10+** and the `sqlite3` command-line program.
- [Ollama](https://ollama.com/download), installed and running.
- [Claude Code](https://code.claude.com/docs/en/setup), installed. The example uses
  `--bare`, manual permissions and the Anthropic-compatible API; the original harness
  was tested with Claude Code 2.1.272 and Ollama 0.34.0.
- Enough free memory for `gpt-oss:20b`. Its weights alone are approximately 13 GB;
  model context and other applications need additional memory.

**Memory matters.** An early 64k-context experiment coincided with a 24 GB laptop
becoming unresponsive. This example defaults to **16k context and 4,096 output tokens**
and refuses to launch while another model is loaded. That reduces pressure, but is
not a guarantee that a 20B model fits your machine. Close other model sessions and
watch memory usage. No setup or test command performs inference automatically.

## Quick start

```bash
git clone https://github.com/your-online/ollama-claude-code-example.git
cd ollama-claude-code-example

# Explicit, one-time download. Skip if these weights are already installed.
ollama pull gpt-oss:20b

# Generate synthetic data and create a small-context alias. No inference.
python3 -m local_demo init
python3 -m local_demo setup
python3 -m local_demo check

# Open the ordinary Claude Code interface. Your questions trigger inference.
python3 -m local_demo chat
```

The model alias is `local-claude-example`. The launcher runs in `playground/` and
keeps its own configuration in ignored `.local/claude/`. It does not change your
global Claude Code settings or original Ollama model configuration. Re-running
`setup` updates this example's alias; re-running `init` preserves existing data.

If asked **“Do you want to use this API key?”**, choose **Yes**. The key is the dummy
value `ollama`; requests go to `http://127.0.0.1:11434`. No paid Anthropic API key is
needed. Use `/status` to inspect the session and `/exit` to close it.

After use, release the model's memory explicitly:

```bash
ollama stop local-claude-example
```

## Try the SQL exercise

Paste into Claude Code:

```text
Investigate ../data/commerce.sqlite using sqlite3 -readonly through Bash.
Which five customers had the highest net revenue in Q1 2026, after discounts
and returns?

Discover the schema yourself and actually execute the SQL. Include only
completed orders. Money is EUR cents; discount_bps is basis points.
Round discounted line amounts to whole cents. Attribute refunds to the
original order date, including refunds received after the quarter.
Avoid double counting across one-to-many joins.

Show customer name, region and net revenue in euros, highest first.
Break ties by customer ID ascending. Also show the SQL you executed.
Use result columns customer_name, region_name and net_revenue_eur.
Read only the database, not saved answers or validation code. Change nothing.
```

Save the SQL it actually executed as `playground/candidate.sql`, then check it from
the repository root:

```bash
python3 -m local_demo verify-query playground/candidate.sql
```

The verifier independently aggregates raw rows in Python using integer cents. It
does not ask another model. Exit code 0 means the five ordered result rows match;
1 means a mismatch or error. Matching this fixture proves the result, **not that the
SQL is correct for every possible dataset**. A fabricated constant result could
also match; inspect the visible Bash call and use the fresh-code test below to
demonstrate actual retrieval.

## Demonstrate offline retrieval

See [the offline walkthrough](docs/offline.md). In short: prepare the software and
weights, disconnect internet yourself, generate a **new random code** with
`python3 -m local_demo challenge`, and ask Claude Code to retrieve it from SQLite.
Check the returned code with `python3 -m local_demo check-code RETURNED_CODE`.

Neither command loads a model; only the question you send in Claude Code does.
Opening this repository never changes Wi-Fi, firewall or network settings.

## What is in the database?

15 related tables: customers, regions, employees, products, categories, suppliers,
warehouses, inventory, orders, order_items, payments, shipments, returns, tickets
and audit_challenges. There are 180 customers, 96 products, 2,400 orders and about
17,000 rows in total. Dates span January 2025 through August 2026.

Partial payments, split shipments, discounts, cancellations and late returns make
naive joins and date filters produce wrong results. The business fixture is seeded
for reproducibility; challenge codes use cryptographic randomness. All data is
synthetic. Databases and model outputs are generated locally and never committed.

More details: [architecture and data rules](docs/architecture.md),
[validation and limitations](docs/validation.md), [contributing](CONTRIBUTING.md).

## Development

Runtime uses only the Python standard library. Tests run without Ollama, Claude Code,
internet, model weights or a GPU:

```bash
make test

# Optional development tooling: install uv, then install the pinned lint dependency.
uv sync --group dev
make lint
```

This repository is a runnable example, not a published Python distribution: run
commands from the checkout. `--workspace PATH` before the subcommand selects a
different data/playground/config directory.

## Why this model and harness?

The original local experiment successfully used `gpt-oss:20b` to invoke Claude Code's
Bash tool and retrieve a freshly generated SQLite value. A subsequent revenue answer
was independently checked against every relevant customer total. An attempted
DeepSeek-R1 setup had native tool-template compatibility problems, so DeepSeek is
not the default in this example.

Claude Code remains the interface and tool executor; the model runs in Ollama.
The wrapper sets local provider/model roles, disables known nonessential traffic,
and omits cloud/MCP integrations. **This is not a network sandbox**: Bash can run
network commands, and organization-managed settings may still apply. Physically
disconnect internet for the strongest straightforward demonstration. Keep normal
permissions enabled and use synthetic data.

Official references: [Ollama + Claude Code](https://docs.ollama.com/integrations/claude-code),
[Anthropic API compatibility](https://docs.ollama.com/api/anthropic-compatibility),
[Claude Code environment variables](https://code.claude.com/docs/en/env-vars).

## License

MIT for this example's code. Claude Code, Ollama and downloaded model weights retain
their own licenses and terms. This repository is not affiliated with their vendors.
