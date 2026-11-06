# PyMOL QuickVisuals

Control [PyMOL](https://pymol.org) by talking to Claude. Ask for what you want to see, such as *"show the heme pocket of hemoglobin, protein in cyan, ligands as yellow spheres"*. Claude runs the PyMOL commands, **takes a screenshot to check the result**, and fixes what doesn't look right.

PyMOL QuickVisuals is an [MCP](https://modelcontextprotocol.io) server. It works with Claude Code and any other MCP client.

## What makes it different

- **Claude sees its own work.** The `screenshot` tool returns the current view as an image, so Claude can check a figure before telling you it's done.
- **Real errors.** PyMOL's remote interface normally hides failures. PyMOL QuickVisuals reports the actual message and which command failed, so Claude fixes the cause instead of guessing.
- **Starts PyMOL for you.** If PyMOL isn't running, it is found and launched with remote control enabled. No flags to remember.
- **Windows-first.** It finds Schrödinger and open-source PyMOL installs on Windows, macOS and Linux. Run `pymol-quickvisuals doctor` to check your setup.
- **Made for teaching.** It has a structure summary tool (chains, ligands, ions, waters) and built-in guidance that asks Claude to explain the biology, not just run commands. See [`workshop/`](workshop/).

## Install

You need Python 3.10+, PyMOL, and [Claude Code](https://claude.com/claude-code).

```bash
pip install git+https://github.com/OmarArias-Gaguancela/pymol-quickvisuals
pymol-quickvisuals setup
pymol-quickvisuals doctor
```

`setup` registers the server with Claude Code for all your projects. Start a new Claude Code session and ask it to show you a protein.

Using another MCP client? Point it at `python -m pymol_quickvisuals` as a stdio server.

## Tools

| Tool | What it does |
|---|---|
| `pymol_status` | Connects (starting PyMOL if needed) and lists loaded objects |
| `run_commands` | Runs a list of PyMOL commands in order and stops at the first error |
| `run_python` | Runs Python inside PyMOL (`cmd`, `stored` available); printed output is returned |
| `query` | Calls one `cmd` function and returns its value (`count_atoms`, `get_chains`, `get_fastastr`, …) |
| `describe_structure` | Lists chains, residue counts, ligands/ions with locations, and waters |
| `screenshot` | Returns the current view as an image; `ray=True` for publication quality |

## Configuration

| Environment variable | Default | Meaning |
|---|---|---|
| `PYMOL_PATH` | auto-detected | Path to the PyMOL executable |
| `PYMOL_RPC_URL` | `http://localhost:9123` | Where PyMOL's remote control listens |
| `PYMOL_QV_AUTOSTART` | `1` | Set to `0` to never launch PyMOL automatically |
| `PYMOL_QV_TIMEOUT` | `300` | Seconds to wait for PyMOL to answer one request |

To start PyMOL yourself with remote control enabled, run `pymol-quickvisuals launch` or `pymol -R`.

## How it works

PyMOL has a built-in XML-RPC server. PyMOL QuickVisuals sends each request as a small script that PyMOL runs. The script captures output and errors and writes them to a temporary file that the server reads back. Because of this, PyMOL and the server must run on the same computer.

## License

MIT © Omar Arias-Gaguancela
