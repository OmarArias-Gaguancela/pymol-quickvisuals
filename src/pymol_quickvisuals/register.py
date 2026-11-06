"""Register this server with Claude Code and Claude Desktop.

Works without the `claude` command line tool: if it is missing, the config
files are edited directly (a .bak copy is kept the first time).
"""

from __future__ import annotations

import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile

SERVER_NAME = "pymol-quickvisuals"


def server_entry() -> dict:
    return {"command": sys.executable, "args": ["-m", "pymol_quickvisuals"]}


def claude_cli() -> str | None:
    return shutil.which("claude")


def claude_code_config() -> str:
    base = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~")
    return os.path.join(base, ".claude.json")


def desktop_configs() -> list[str]:
    """claude_desktop_config.json paths for every Claude Desktop install found."""
    dirs: list[str] = []
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA", "")
        local = os.environ.get("LOCALAPPDATA", "")
        dirs.append(os.path.join(appdata, "Claude"))
        # Microsoft Store install: the app reads a redirected copy of AppData.
        dirs += glob.glob(os.path.join(local, "Packages", "Claude_*", "LocalCache", "Roaming", "Claude"))
    elif sys.platform == "darwin":
        dirs.append(os.path.expanduser("~/Library/Application Support/Claude"))
    else:
        dirs.append(os.path.join(os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")), "Claude"))
    return [os.path.join(d, "claude_desktop_config.json") for d in dirs if d and os.path.isdir(d)]


def _read(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        text = f.read().strip()
    if not text:
        return {}
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("unexpected format")
    return data


def _write(path: str, data: dict) -> None:
    if os.path.exists(path) and not os.path.exists(path + ".bak"):
        shutil.copy2(path, path + ".bak")
    folder = os.path.dirname(path) or "."
    os.makedirs(folder, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=folder, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)


def _set_server(path: str, entry: dict) -> None:
    data = _read(path)
    servers = data.setdefault("mcpServers", {})
    if not isinstance(servers, dict):
        raise ValueError("'mcpServers' is not an object")
    servers[SERVER_NAME] = entry
    _write(path, data)


def is_registered(path: str) -> bool:
    try:
        return SERVER_NAME in (_read(path).get("mcpServers") or {})
    except (OSError, ValueError):
        return False


def register_claude_code(scope: str = "user") -> str:
    """Returns a status line. Raises RuntimeError on failure."""
    entry = server_entry()
    cli = claude_cli()
    if cli:
        subprocess.run([cli, "mcp", "remove", SERVER_NAME, "-s", scope], capture_output=True)
        r = subprocess.run([cli, "mcp", "add", SERVER_NAME, "-s", scope, "--", entry["command"], *entry["args"]],
                           capture_output=True, text=True)
        if r.returncode == 0:
            return f"Claude Code: registered ({scope} scope)."
        if scope != "user":
            raise RuntimeError(f"Claude Code: `claude mcp add` failed: {(r.stderr or r.stdout).strip()}")
    elif scope != "user":
        raise RuntimeError("Claude Code: --scope needs the `claude` command line tool.")
    path = claude_code_config()
    try:
        _set_server(path, {"type": "stdio", **entry, "env": {}})
    except (OSError, ValueError) as e:
        raise RuntimeError(f"Claude Code: could not update {path}: {e}") from e
    return f"Claude Code: registered in {path}."


def register_desktop() -> list[str]:
    """Returns status lines (empty if Claude Desktop was not found)."""
    lines = []
    for path in desktop_configs():
        try:
            _set_server(path, server_entry())
            lines.append(f"Claude Desktop: registered in {path}.")
        except (OSError, ValueError) as e:
            lines.append(f"Claude Desktop: could not update {path}: {e}")
    return lines
