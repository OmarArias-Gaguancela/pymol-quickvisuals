"""Command line entry point.

    pymol-quickvisuals            run the MCP server (what Claude Code launches)
    pymol-quickvisuals setup      register the server with Claude Code and Claude Desktop
    pymol-quickvisuals doctor     check that everything is in place
    pymol-quickvisuals launch     start PyMOL with remote control enabled
"""

from __future__ import annotations

import argparse
import sys

from . import __version__, bridge, launcher, register


def setup(scope: str, code: bool, desktop: bool) -> int:
    failed = False
    if code:
        try:
            print(register.register_claude_code(scope))
        except RuntimeError as e:
            print(e)
            failed = True
    if desktop:
        lines = register.register_desktop()
        if lines:
            print("\n".join(lines))
            failed |= any("could not" in line for line in lines)
        else:
            print("Claude Desktop: not installed, skipped.")
    if failed:
        return 1
    print()
    print("Done. Restart Claude Desktop (or start a new Claude Code session),")
    print("then ask Claude to show you a protein.")
    return 0


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
    hint = "Run: python -m pymol_quickvisuals setup"
    code_cfg = register.claude_code_config()
    desk_cfgs = register.desktop_configs()
    code_ok = register.is_registered(code_cfg)
    desk_ok = any(register.is_registered(p) for p in desk_cfgs)
    print(f"[{'ok' if code_ok else '--'}] Claude Code: {'registered' if code_ok else 'not registered'}")
    if desk_cfgs:
        print(f"[{'ok' if desk_ok else '--'}] Claude Desktop: {'registered' if desk_ok else 'not registered'}")
    check("Registered with at least one Claude app", code_ok or desk_ok, hint)
    print("All good." if ok else "Fix the items marked !! above.")
    return 0 if ok else 1


def main() -> None:
    p = argparse.ArgumentParser(prog="pymol-quickvisuals", description="Control PyMOL from Claude.")
    p.add_argument("--version", action="version", version=f"pymol-quickvisuals {__version__}")
    sub = p.add_subparsers(dest="command")
    s = sub.add_parser("setup", help="register the server with Claude Code and Claude Desktop")
    s.add_argument("--scope", default="user", choices=["user", "project", "local"],
                   help="Claude Code scope (project/local need the `claude` command)")
    only = s.add_mutually_exclusive_group()
    only.add_argument("--code-only", action="store_true", help="only register with Claude Code")
    only.add_argument("--desktop-only", action="store_true", help="only register with Claude Desktop")
    sub.add_parser("doctor", help="check the installation")
    sub.add_parser("launch", help="start PyMOL with remote control enabled")
    args = p.parse_args()

    if args.command == "setup":
        sys.exit(setup(args.scope, code=not args.desktop_only, desktop=not args.code_only))
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
