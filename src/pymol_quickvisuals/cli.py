"""Command line entry point.

    pymol-quickvisuals            run the MCP server (what Claude Code launches)
    pymol-quickvisuals setup      register the server with Claude Code
    pymol-quickvisuals doctor     check that everything is in place
    pymol-quickvisuals launch     start PyMOL with remote control enabled
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys

from . import __version__, bridge, launcher

SERVER_NAME = "pymol-quickvisuals"


def _claude() -> str | None:
    return shutil.which("claude")


def setup(scope: str) -> int:
    claude = _claude()
    cmd = [sys.executable, "-m", "pymol_quickvisuals"]
    if not claude:
        print("Claude Code CLI ('claude') not found on PATH.")
        print("Add this server manually with:")
        print(f"  claude mcp add {SERVER_NAME} -s {scope} -- " + " ".join(f'"{c}"' for c in cmd))
        return 1
    subprocess.run([claude, "mcp", "remove", SERVER_NAME, "-s", scope], capture_output=True)
    r = subprocess.run([claude, "mcp", "add", SERVER_NAME, "-s", scope, "--", *cmd])
    if r.returncode == 0:
        print(f"Registered '{SERVER_NAME}' with Claude Code ({scope} scope).")
        print("Start a new Claude Code session and ask it to show you a protein.")
    return r.returncode


def doctor() -> int:
    ok = True

    def check(label: str, passed: bool, hint: str = "") -> None:
        nonlocal ok
        ok &= passed
        print(f"[{'ok' if passed else '!!'}] {label}" + (f"\n     {hint}" if hint and not passed else ""))

    check(f"Python {sys.version.split()[0]}", sys.version_info >= (3, 10), "Python 3.10+ is required.")
    try:
        import mcp  # noqa: F401
        check("mcp package installed", True)
    except ImportError:
        check("mcp package installed", False, "pip install mcp")
    exe = launcher.find_pymol()
    check(f"PyMOL found: {exe}" if exe else "PyMOL found", bool(exe),
          "Install PyMOL or set PYMOL_PATH to its executable.")
    running = launcher.port_open(bridge._host, bridge._port)
    print(f"[--] PyMOL remote control at {bridge.URL}: {'running' if running else 'not running (starts automatically)'}")
    check("Claude Code CLI found", bool(_claude()), "Install Claude Code, or add the server in your MCP client's config.")
    print("All good." if ok else "Fix the items marked !! above.")
    return 0 if ok else 1


def main() -> None:
    p = argparse.ArgumentParser(prog="pymol-quickvisuals", description="Control PyMOL from Claude.")
    p.add_argument("--version", action="version", version=f"pymol-quickvisuals {__version__}")
    sub = p.add_subparsers(dest="command")
    s = sub.add_parser("setup", help="register the server with Claude Code")
    s.add_argument("--scope", default="user", choices=["user", "project", "local"])
    sub.add_parser("doctor", help="check the installation")
    sub.add_parser("launch", help="start PyMOL with remote control enabled")
    args = p.parse_args()

    if args.command == "setup":
        sys.exit(setup(args.scope))
    if args.command == "doctor":
        sys.exit(doctor())
    if args.command == "launch":
        try:
            print(launcher.launch(bridge._host, bridge._port))
        except RuntimeError as e:
            print(e)
            sys.exit(1)
        return
    from .server import main as serve
    serve()
