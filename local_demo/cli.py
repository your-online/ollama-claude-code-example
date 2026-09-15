"""Small setup/verification CLI. Only the explicit chat command runs inference."""

import argparse
import hmac
import json
import secrets
import sqlite3
import subprocess
import sys
from pathlib import Path

from .audit import verify_query
from .database import generate_database
from .runtime import (
    MODEL_ALIAS,
    launch,
    ollama_api,
    require_commands,
    require_local_model,
    setup_model,
)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init", help="Generate dummy data; no model or network.")
    init.add_argument("--seed", type=int, default=20260915)
    commands.add_parser(
        "setup", help="Create an alias of already downloaded model weights; no inference."
    )
    commands.add_parser("check", help="Inspect local prerequisites/server; no model is loaded.")
    commands.add_parser("chat", help="Start Claude Code. Your questions trigger local inference.")
    commands.add_parser("challenge", help="Write a fresh random code and print a retrieval prompt.")
    check_code = commands.add_parser(
        "check-code", help="Compare the model's answer without running a model."
    )
    check_code.add_argument("code")
    audit = commands.add_parser(
        "verify-query", help="Compare submitted SQL with an independent calculation."
    )
    audit.add_argument("file", type=Path)
    args = parser.parse_args(argv)
    workspace = args.workspace.resolve()
    database = workspace / "data" / "commerce.sqlite"
    try:
        if args.command == "init":
            if database.exists():
                print(f"Existing database preserved: {database}")
            else:
                generate_database(database, args.seed)
                print(f"Generated 15-table synthetic database: {database}")
        elif args.command == "setup":
            setup_model()
            print(f"Created {MODEL_ALIAS}. No model loaded or inference performed.")
        elif args.command == "check":
            require_commands()
            info = require_local_model(MODEL_ALIAS)
            print(
                json.dumps(
                    {
                        "database_exists": database.is_file(),
                        "model": MODEL_ALIAS,
                        "capabilities": info.get("capabilities"),
                        "loaded_models": ollama_api("/api/ps").get("models", []),
                    },
                    indent=2,
                )
            )
        elif args.command == "chat":
            return launch(workspace)
        elif args.command == "verify-query":
            result = verify_query(database, args.file.read_text())
            print(json.dumps(result, indent=2))
            return 0 if result["matches"] else 1
        elif args.command == "challenge":
            if not database.is_file():
                raise RuntimeError("Run init first.")
            with sqlite3.connect(database) as con:
                con.execute(
                    "INSERT INTO audit_challenges VALUES ('fresh-proof', ?) "
                    "ON CONFLICT(label) DO UPDATE SET secret_code=excluded.secret_code",
                    (secrets.token_hex(12),),
                )
            con.close()
            print("A fresh random code was saved; it is not included below. Ask Claude Code:\n")
            print(
                "Use Bash to execute: sqlite3 -readonly ../data/commerce.sqlite "
                "\"SELECT secret_code FROM audit_challenges WHERE label='fresh-proof'\". "
                "Return the exact retrieved code. Read no logs or saved answers."
            )
        elif args.command == "check-code":
            con = sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)
            try:
                row = con.execute(
                    "SELECT secret_code FROM audit_challenges WHERE label='fresh-proof'"
                ).fetchone()
            finally:
                con.close()
            if not row:
                raise RuntimeError("Run challenge first.")
            matches = hmac.compare_digest(args.code.strip().encode(), row[0].encode())
            print("PASS: exact fresh code." if matches else "FAIL: the code does not match.")
            return 0 if matches else 1
        return 0
    except (
        OSError,
        RuntimeError,
        ValueError,
        sqlite3.Error,
        sqlite3.Warning,
        subprocess.CalledProcessError,
    ) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
