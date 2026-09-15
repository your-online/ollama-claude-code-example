"""Local-only preflight checks and a process-scoped Claude Code launcher."""

import json
import os
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

OLLAMA_URL = "http://127.0.0.1:11434"
MODEL_ALIAS = "local-claude-example"
BASE_MODEL = "gpt-oss:20b"
CONTEXT_LENGTH = 16384
MAX_OUTPUT_TOKENS = 4096


def ollama_api(endpoint, payload=None):
    data = None if payload is None else json.dumps(payload).encode()
    request = urllib.request.Request(
        OLLAMA_URL + endpoint, data=data, headers={"Content-Type": "application/json"}
    )
    # Never route loopback requests through inherited corporate/cloud proxies.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(request, timeout=10) as response:
            return json.load(response)
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        raise RuntimeError(f"Local Ollama unavailable: {exc}. Start Ollama first.") from exc


def require_local_model(name):
    info = ollama_api("/api/show", {"model": name})
    if "cloud" in name.lower() or info.get("remote_host") or info.get("remote_model"):
        raise RuntimeError("This example refuses cloud models and remote model aliases.")
    if "tools" not in info.get("capabilities", []):
        raise RuntimeError(f"{name} does not advertise tool support.")
    return info


def require_commands():
    for name in ("ollama", "claude", "sqlite3"):
        if shutil.which(name) is None:
            raise RuntimeError(f"Missing {name}. See the README prerequisites.")


def setup_model():
    require_commands()
    require_local_model(BASE_MODEL)  # Fails if not downloaded; never pulls implicitly.
    modelfile = (
        f"FROM {BASE_MODEL}\nPARAMETER num_ctx {CONTEXT_LENGTH}\n"
        f"PARAMETER num_predict {MAX_OUTPUT_TOKENS}\n"
    )
    with tempfile.TemporaryDirectory(prefix="ollama-claude-setup-") as directory:
        path = Path(directory) / "Modelfile"
        path.write_text(modelfile)
        subprocess.run(
            ["ollama", "create", MODEL_ALIAS, "-f", str(path)],
            text=True,
            check=True,
            env={**os.environ, "OLLAMA_HOST": OLLAMA_URL},
        )


def launch_environment(workspace, inherited=None):
    source = os.environ if inherited is None else inherited
    env = {
        key: value
        for key, value in source.items()
        if not key.startswith(("ANTHROPIC_", "OTEL_", "CLAUDE_CODE_USE_"))
        and key not in {"CLAUDECODE", "CLAUDE_CODE_OAUTH_TOKEN", "CLAUDE_CODE_ENABLE_TELEMETRY"}
    }
    env.update(
        {
            "ANTHROPIC_BASE_URL": OLLAMA_URL,
            "ANTHROPIC_API_KEY": "ollama",  # Dummy value required by Claude Code --bare.
            "ANTHROPIC_AUTH_TOKEN": "ollama",
            "ANTHROPIC_MODEL": MODEL_ALIAS,
            "ANTHROPIC_DEFAULT_OPUS_MODEL": MODEL_ALIAS,
            "ANTHROPIC_DEFAULT_SONNET_MODEL": MODEL_ALIAS,
            "ANTHROPIC_DEFAULT_HAIKU_MODEL": MODEL_ALIAS,
            "ANTHROPIC_SMALL_FAST_MODEL": MODEL_ALIAS,
            "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
            "CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS": "1",
            "CLAUDE_CODE_DISABLE_OFFICIAL_MARKETPLACE_AUTOINSTALL": "1",
            "ENABLE_CLAUDEAI_MCP_SERVERS": "false",
            "CLAUDE_CONFIG_DIR": str(workspace / ".local" / "claude"),
            "CLAUDE_CODE_MAX_OUTPUT_TOKENS": str(MAX_OUTPUT_TOKENS),
            "API_TIMEOUT_MS": "600000",
            "NO_PROXY": "127.0.0.1,localhost,::1",
            "no_proxy": "127.0.0.1,localhost,::1",
        }
    )
    return env


def launch_command():
    return [
        "claude",
        "--bare",
        "--model",
        MODEL_ALIAS,
        "--effort",
        "low",
        "--permission-mode",
        "manual",
        "--setting-sources",
        "",
        "--strict-mcp-config",
        "--mcp-config",
        '{"mcpServers":{}}',
        "--no-chrome",
        "--tools",
        "Bash,Read,Write,Edit,Glob,Grep",
        "--append-system-prompt",
        Path(__file__).with_name("context.md").read_text(),
    ]


def launch(workspace):
    require_commands()
    require_local_model(MODEL_ALIAS)
    running = ollama_api("/api/ps").get("models", [])
    others = [
        m.get("name", "unknown")
        for m in running
        if m.get("name") not in {MODEL_ALIAS, MODEL_ALIAS + ":latest"}
    ]
    if others:
        raise RuntimeError(
            "Other models are loaded: "
            + ", ".join(others)
            + ". Stop them explicitly with 'ollama stop MODEL' before this demo."
        )
    help_text = subprocess.run(
        ["claude", "--help"], capture_output=True, text=True, check=True
    ).stdout
    if "--bare" not in help_text or "--permission-mode" not in help_text:
        raise RuntimeError(
            "Update Claude Code: this launcher requires --bare and manual permissions."
        )
    if not (workspace / "data" / "commerce.sqlite").is_file():
        raise RuntimeError("Database missing. Run 'python3 -m local_demo init' first.")
    playground = workspace / "playground"
    playground.mkdir(exist_ok=True)
    (workspace / ".local" / "claude").mkdir(parents=True, exist_ok=True)
    print(f"Claude Code → {OLLAMA_URL} → {MODEL_ALIAS}", flush=True)
    print("16k context; model weights still require substantial RAM. Exit with /exit.", flush=True)
    return subprocess.call(launch_command(), cwd=playground, env=launch_environment(workspace))
