"""Termux/Android runtime preload self-heal (Issue #51).

Root cause: the PyPI `cryptography` wheel's Rust extension
(`_rust.abi3.so`) has no DT_NEEDED entry for libpython, so on
Android's linker the `PyLong_Type` symbol is unresolvable unless
libpython is preloaded via LD_PRELOAD at exec time. The canonical
`.venv/bin/yasinrelay-termux` launcher already does this, but direct
invocations (`.venv/bin/python -m yasinrelay.cli`, `pytest`) do not.

This helper re-execs the current process with libpython prepended to
LD_PRELOAD when running on Termux and the preload is missing. It is a
no-op on non-Termux/CI environments. Post-start `ctypes.CDLL(RTLD_GLOBAL)`
does NOT fix the Android linker state, so re-exec is required.
"""

from __future__ import annotations

import os
import sys


def libpython_path(prefix: str | None = None) -> str | None:
    pref = prefix or os.environ.get("PREFIX", "/data/data/com.termux/files/usr")
    if pref != "/data/data/com.termux/files/usr":
        return None
    lib = os.path.join(
        pref, "lib", f"libpython{sys.version_info.major}.{sys.version_info.minor}.so"
    )
    if os.path.isfile(lib):
        return lib
    return None


def ensure_termux_preload() -> None:
    """Re-exec with libpython preloaded on Termux when missing.

    Guarded by `_YASINRELAY_PRELOAD_FIXED` to avoid loops. Only acts when:
    - running on Termux (PREFIX + libpython file present), and
    - current LD_PRELOAD does not already contain that libpython.
    """
    if os.environ.get("_YASINRELAY_PRELOAD_FIXED") == "1":
        return
    lib = libpython_path()
    if lib is None:
        return
    current = os.environ.get("LD_PRELOAD", "")
    if lib in current.split(":"):
        return
    env = dict(os.environ)
    env["LD_PRELOAD"] = f"{lib}:{current}" if current else lib
    env["_YASINRELAY_PRELOAD_FIXED"] = "1"
    try:
        orig = list(getattr(sys, "orig_argv", []))
        if len(orig) >= 2:
            # orig_argv[0] is the original executable as invoked; reuse the
            # resolved interpreter with the exact original arguments so that
            # `-c`, `-m`, script paths and their arguments survive re-exec.
            argv = [sys.executable, *orig[1:]]
        else:
            argv = [sys.executable, *sys.argv]
        os.execve(sys.executable, argv, env)
    except Exception:
        return
