"""Connection to a running PyMOL via its built-in XML-RPC server.

PyMOL's `cmd.do()` swallows errors, so code is run inside PyMOL through a small
wrapper script that captures printed output and exceptions and writes them to
a JSON file. PyMOL and this server must therefore share a filesystem.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import uuid
import xmlrpc.client
from urllib.parse import urlparse

from . import launcher

URL = os.environ.get("PYMOL_RPC_URL", "http://localhost:9123")
AUTOSTART = os.environ.get("PYMOL_QV_AUTOSTART", "1") not in ("0", "false", "no")

_host = urlparse(URL).hostname or "localhost"
_port = urlparse(URL).port or 9123

# Lines PyMOL prints on failure: " Error:", "Selector-Error:", "NameError:", ...
ERROR_RE = re.compile(r"(^|\s|-)\w*Error\b|^Traceback", re.MULTILINE)


class PyMOLError(Exception):
    """A failure the model should see and act on."""


_SCRIPT = '''\
import io as _qv_io, sys as _qv_sys, json as _qv_json, traceback as _qv_tb
from pymol import cmd, stored
_qv_buf = _qv_io.StringIO()
_qv_out, _qv_err = _qv_sys.stdout, _qv_sys.stderr
_qv_sys.stdout = _qv_sys.stderr = _qv_buf
_qv_res = {{"ok": True, "step": None}}
try:
    for _qv_i, _qv_src in enumerate({steps!r}):
        _qv_res["step"] = _qv_i
        _qv_mark = _qv_buf.tell()
        if {mode!r} == "commands":
            cmd.do(_qv_src)
            if _qv_re.search(_qv_buf.getvalue()[_qv_mark:]):
                _qv_res["ok"] = False
                break
        else:
            exec(compile(_qv_src, "<claude>", "exec"), globals())
except BaseException:
    _qv_res["ok"] = False
    _qv_res["error"] = _qv_tb.format_exc()
finally:
    _qv_sys.stdout, _qv_sys.stderr = _qv_out, _qv_err
_qv_res["output"] = _qv_buf.getvalue()
with open({result!r}, "w", encoding="utf-8") as _qv_f:
    _qv_f.write(_qv_json.dumps(_qv_res))
'''

_PRELUDE = f"import re as _qv_rem\n_qv_re = _qv_rem.compile({ERROR_RE.pattern!r}, _qv_rem.MULTILINE)\n"


def tmp_path(suffix: str) -> str:
    name = f"pymol_qv_{uuid.uuid4().hex}{suffix}"
    return os.path.join(tempfile.gettempdir(), name).replace("\\", "/")


TIMEOUT = float(os.environ.get("PYMOL_QV_TIMEOUT", "300"))


class _Transport(xmlrpc.client.Transport):
    def make_connection(self, host):
        conn = super().make_connection(host)
        conn.timeout = TIMEOUT
        return conn


def _proxy() -> xmlrpc.client.ServerProxy:
    return xmlrpc.client.ServerProxy(URL, allow_none=True, transport=_Transport())


def ensure_running() -> str | None:
    """Make sure PyMOL is reachable; start it if allowed. Returns a note if it was started."""
    if launcher.port_open(_host, _port):
        return None
    if not AUTOSTART:
        raise PyMOLError(f"PyMOL is not running at {URL}. Start it with `pymol -R`.")
    try:
        return launcher.launch(_host, _port)
    except RuntimeError as e:
        raise PyMOLError(str(e)) from e


def call(method: str, *args):
    """Call a `cmd` function directly over XML-RPC."""
    ensure_running()
    try:
        return getattr(_proxy(), method)(*args)
    except xmlrpc.client.Fault as e:
        msg = e.faultString.split(">:", 1)[-1].strip() or f"{method} failed"
        raise PyMOLError(msg) from None
    except OSError as e:
        raise PyMOLError(f"Lost connection to PyMOL: {e}") from None


def execute(steps: list[str], mode: str) -> dict:
    """Run PyMOL commands (mode="commands") or Python snippets (mode="python") inside PyMOL.

    Stops at the first failing step. Returns {ok, output, error?, step}.
    """
    ensure_running()
    script, result = tmp_path(".py"), tmp_path(".json")
    with open(script, "w", encoding="utf-8") as f:
        f.write(_PRELUDE + _SCRIPT.format(steps=list(steps), mode=mode, result=result))
    try:
        try:
            _proxy().run(script)
        except xmlrpc.client.Fault as e:
            raise PyMOLError(f"PyMOL could not run the request: {e.faultString}") from None
        except TimeoutError:
            raise PyMOLError(f"PyMOL did not answer within {TIMEOUT:.0f}s (busy, or a dialog is open?).") from None
        except OSError as e:
            raise PyMOLError(f"Lost connection to PyMOL: {e}") from None
        if not os.path.exists(result):
            raise PyMOLError("PyMOL returned no result (is a dialog open in PyMOL?).")
        with open(result, encoding="utf-8") as f:
            return json.load(f)
    finally:
        for p in (script, result):
            try:
                os.remove(p)
            except OSError:
                pass
