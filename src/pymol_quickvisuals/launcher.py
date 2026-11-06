"""Find a PyMOL installation and start it with its XML-RPC server enabled."""

from __future__ import annotations

import glob
import os
import shutil
import socket
import subprocess
import sys
import time


def _candidates() -> list[str]:
    paths: list[str] = []
    env = os.environ.get("PYMOL_PATH")
    if env:
        paths.append(env)

    if sys.platform == "win32":
        local = os.environ.get("LOCALAPPDATA", "")
        roots = [
            os.path.join(local, "Schrodinger", "PyMOL2"),
            os.path.join(local, "Schrodinger", "PyMOL3"),
            os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "PyMOL"),
            os.path.join(os.environ.get("ProgramData", r"C:\ProgramData"), "PyMOL"),
            os.path.join(os.path.expanduser("~"), "PyMOL"),
        ]
        roots += glob.glob(os.path.join(local, "Schrodinger", "PyMOL*"))
        for root in roots:
            paths.append(os.path.join(root, "PyMOLWin.exe"))
            paths.append(os.path.join(root, "Scripts", "pymol.exe"))
    elif sys.platform == "darwin":
        paths += glob.glob("/Applications/PyMOL*.app/Contents/MacOS/PyMOL")
        paths += glob.glob(os.path.expanduser("~/Applications/PyMOL*.app/Contents/MacOS/PyMOL"))

    on_path = shutil.which("pymol")
    if on_path:
        paths.append(on_path)
    return paths


def find_pymol() -> str | None:
    """Return the path of a PyMOL executable, or None."""
    for path in _candidates():
        if path and os.path.isfile(path):
            return path
    return None


def port_open(host: str, port: int, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


# When this process last launched PyMOL. PyMOLWin.exe is a stub that exits at
# once, so the child's own lifetime can't tell us whether PyMOL is still starting.
_launched_at: float | None = None
STARTUP_GRACE = 180.0


def launch(host: str, port: int, wait: float = 90.0) -> str:
    """Start PyMOL with its XML-RPC server on `port` and wait until it answers.

    Never starts a second copy while a recent launch may still be starting.
    Returns a human-readable status line. Raises RuntimeError on failure.
    """
    global _launched_at
    if port_open(host, port):
        return f"PyMOL is already running on {host}:{port}."

    if _launched_at is None or time.time() - _launched_at > STARTUP_GRACE:
        exe = find_pymol()
        if not exe:
            raise RuntimeError(
                "Could not find PyMOL. Install it, or set the PYMOL_PATH environment "
                "variable to the PyMOL executable (e.g. PyMOLWin.exe)."
            )
        # Start the RPC server on exactly this port. (`pymol -R` picks the first
        # free port from 9123, and on Windows two copies can share 9123.)
        startup = f"/import pymol.rpc; pymol.rpc.launch_XMLRPC(port={int(port)}, nToTry=1)"
        kwargs: dict = dict(stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if sys.platform == "win32":
            # Detach so PyMOL outlives this server; never share our stdio (the MCP channel).
            kwargs["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            kwargs["start_new_session"] = True
        subprocess.Popen([exe, "-d", startup], **kwargs)
        _launched_at = time.time()
        note = f"Started PyMOL ({exe}) on {host}:{port}."
    else:
        note = f"PyMOL is starting up on {host}:{port}."

    deadline = time.time() + wait
    while time.time() < deadline:
        if port_open(host, port):
            time.sleep(1.0)  # let PyMOL finish initialising
            return note
        time.sleep(0.5)
    raise RuntimeError(
        f"PyMOL is running but its remote-control port {port} has not opened yet. "
        "Try again in a moment."
    )
