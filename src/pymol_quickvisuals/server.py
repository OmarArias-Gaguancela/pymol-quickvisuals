"""PyMOL QuickVisuals: an MCP server that lets Claude drive PyMOL and see the result."""

from __future__ import annotations

import functools
import os
import re
import time

from mcp.server.fastmcp import FastMCP, Image

from . import bridge
from .bridge import ERROR_RE, PyMOLError

INSTRUCTIONS = """\
You control a live PyMOL session that the user is watching.

Workflow
- Start with `pymol_status` to see what is loaded. PyMOL is started automatically if it is not running.
- Use `run_commands` for ordinary PyMOL commands (one command per list item). It stops at the first error.
- Use `run_python` for loops, `iterate`, `alter`, or anything needing logic; `cmd` and `stored` are available, print() what you need back.
- Use `query` to read data with a single cmd function (get_names, count_atoms, get_fastastr, get_chains, distance, ...).
- Use `describe_structure` before explaining a structure: it lists chains, ligands, waters and ions.
- After building or changing a view, call `screenshot` and look at it before telling the user it is done. Fix what looks wrong.

Rules
- Any reply starting with "ERROR" means it failed: fix the cause before continuing.
- Check selections with query("count_atoms", ["<sel>"]); 0 atoms means the selection is wrong.
- Object names starting with a digit (e.g. 1hho) are awkward inside selection expressions; prefer chain/resn/polymer selectors.
- End visual workflows with `deselect` so selection markers do not show.
- Use `ray=True` in `screenshot` only for final figures; it is slower.
- When teaching, explain what each step shows biologically, not just which command ran.
"""

mcp = FastMCP("pymol-quickvisuals", instructions=INSTRUCTIONS)


_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _clean_traceback(tb: str) -> str:
    """Drop the wrapper's own frames; keep the user's code and PyMOL's error."""
    lines = tb.strip().splitlines()
    for i, line in enumerate(lines):
        if line.strip().startswith('File "<claude>"'):
            return "Traceback (most recent call last):\n" + "\n".join(lines[i:])
    return "\n".join(lines)


def _report(res: dict, steps: list[str] | None = None) -> str:
    out = _ANSI_RE.sub("", res.get("output") or "").strip()
    if res.get("ok"):
        return out or "OK"
    where = ""
    if steps is not None and res.get("step") is not None:
        i = res["step"]
        where = f" at step {i + 1} ({steps[i]!r})"
        if i == 1:
            where += "; step 1 succeeded"
        elif i > 1:
            where += f"; steps 1-{i} succeeded"
    detail = _clean_traceback(_ANSI_RE.sub("", res.get("error") or ""))
    if not detail and ERROR_RE.search(out):
        detail = out
        out = ""
    msg = f"ERROR{where}:\n{detail}"
    return msg + (f"\nOutput:\n{out}" if out else "")


def _guard(fn):
    @functools.wraps(fn)
    def wrapper(*a, **kw):
        try:
            return fn(*a, **kw)
        except PyMOLError as e:
            return f"ERROR: {e}"
    return wrapper


@mcp.tool()
@_guard
def pymol_status() -> str:
    """Check the PyMOL connection (starting PyMOL if needed) and list loaded objects."""
    note = bridge.ensure_running()
    names = bridge.call("get_names", "objects")
    lines = [note] if note else []
    lines.append(f"Connected to PyMOL at {bridge.URL}.")
    if names:
        for n in names:
            lines.append(f"- {n}: {bridge.call('count_atoms', n)} atoms")
    else:
        lines.append("No objects loaded.")
    return "\n".join(lines)


@mcp.tool()
@_guard
def run_commands(commands: list[str]) -> str:
    """Run PyMOL commands in order, one per item (e.g. ["fetch 1hho", "show sticks, resn HEM"]).

    Stops at the first failing command and reports which one failed.
    """
    commands = [c.strip() for c in commands if c and c.strip()]
    if not commands:
        return "ERROR: no commands given."
    return _report(bridge.execute(commands, "commands"), commands)


@mcp.tool()
@_guard
def run_python(code: str) -> str:
    """Run Python inside PyMOL. `cmd` and `stored` are available; print() values to return them."""
    try:
        compile(code, "<claude>", "exec")
    except SyntaxError as e:
        return f"ERROR: SyntaxError: {e}"
    return _report(bridge.execute([code], "python"))


@mcp.tool()
@_guard
def query(function: str, args: list = []) -> str:
    """Call one PyMOL `cmd` function and return its result, e.g.
    query("count_atoms", ["chain A"]), query("get_fastastr", ["all"]), query("get_chains", ["1hho"])."""
    return str(bridge.call(function, *args))


_DESCRIBE = r'''
import collections
from pymol import cmd
sel = SEL
objs = cmd.get_object_list(sel)
print("Objects:", ", ".join(objs) or "none")
for ch in cmd.get_chains(sel):
    n = cmd.count_atoms(f"({sel}) and chain \"{ch}\" and polymer and name CA")
    print(f"Chain {ch or '-'}: {n} residues")
het = collections.OrderedDict()
cmd.iterate(f"({sel}) and not polymer and not solvent", "het[(resn, chain, resi)] = 1", space={"het": het})
kinds = collections.Counter(k[0] for k in het)
if kinds:
    print("Ligands / ions:", ", ".join(f"{r} x{c}" for r, c in kinds.items()))
    for resn, chain, resi in het:
        print(f"  {resn} {chain}/{resi}")
else:
    print("Ligands / ions: none")
w = cmd.count_atoms(f"({sel}) and solvent")
print(f"Water atoms: {w}")
'''


@mcp.tool()
@_guard
def describe_structure(selection: str = "all") -> str:
    """Summarise what is loaded: objects, chains with residue counts, ligands/ions with locations, waters."""
    return _report(bridge.execute([_DESCRIBE.replace("SEL", repr(selection))], "python"))


@mcp.tool()
@_guard
def screenshot(width: int = 900, height: int = 675, ray: bool = False):
    """Capture the current PyMOL view as an image so you can check the result.
    Set ray=True for a ray-traced, publication-quality image (slower)."""
    path = bridge.tmp_path(".png")
    try:
        res = bridge.execute([f"cmd.png({path!r}, width={int(width)}, height={int(height)}, ray={int(ray)})"], "python")
        deadline = time.time() + 5  # the GUI may write the file on its next redraw
        while res.get("ok") and not os.path.exists(path) and time.time() < deadline:
            time.sleep(0.1)
        if not os.path.exists(path) and not ray:
            # Headless PyMOL cannot grab the OpenGL buffer; ray-trace instead.
            res = bridge.execute([f"cmd.png({path!r}, width={int(width)}, height={int(height)}, ray=1)"], "python")
        if not os.path.exists(path):
            return _report(res) if not res.get("ok") else "ERROR: PyMOL did not write an image."
        with open(path, "rb") as f:
            return Image(data=f.read(), format="png")
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


def main() -> None:
    mcp.run(transport="stdio")
