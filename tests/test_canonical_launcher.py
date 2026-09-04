"""Regression tests for canonical Termux launcher scripts/yasinrelay-termux.

Contract: .venv/bin/yasinrelay-termux run --schedule --non-interactive
"""
from __future__ import annotations

import os
import stat
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAUNCHER_SRC = ROOT / "scripts" / "yasinrelay-termux"
LAUNCHER = ROOT / ".venv" / "bin" / "yasinrelay-termux"


def _run_launcher(args, **kwargs):
    timeout = kwargs.pop("timeout", 15)
    if LAUNCHER.exists():
        cmd = [str(LAUNCHER), *args]
    else:
        cmd = ["bash", str(LAUNCHER_SRC), *args]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, **kwargs)


def test_launcher_source_exists():
    assert LAUNCHER_SRC.exists()
    text = LAUNCHER_SRC.read_text(encoding="utf-8")
    assert "exec" in text
    assert "yasinrelay.cli" in text


def test_launcher_uses_exec_and_no_shell_true():
    text = LAUNCHER_SRC.read_text(encoding="utf-8")
    assert 'exec "$PYTHON_BIN" -m yasinrelay.cli' in text
    assert "shell=True" not in text
    assert "shell = True" not in text


def test_launcher_derives_python_version_dynamically():
    text = LAUNCHER_SRC.read_text(encoding="utf-8")
    assert "sys.version_info" in text
    assert "libpython${PY_VER}.so" in text


def test_launcher_preserves_ld_preload():
    text = LAUNCHER_SRC.read_text(encoding="utf-8")
    assert "LD_PRELOAD" in text
    assert "${LD_PRELOAD:-}" in text or "LD_PRELOAD:-" in text
    assert "LIBPYTHON}:${LD_PRELOAD}" in text or '${LIBPYTHON}:${LD_PRELOAD}' in text


def test_launcher_does_not_use_hardcoded_cwd():
    text = LAUNCHER_SRC.read_text(encoding="utf-8")
    assert "SCRIPT_DIR" in text
    assert "RELAY_ROOT" in text
    assert ".venv/bin/python" in text


def test_launcher_help_propagates():
    result = _run_launcher(["--help"])
    assert result.returncode == 0, result.stderr
    assert "yasinrelay" in result.stdout.lower() or "run" in result.stdout
    result2 = _run_launcher(["run", "--help"])
    assert result2.returncode == 0, result2.stderr
    assert "--schedule" in result2.stdout
    assert "--non-interactive" in result2.stdout


def test_launcher_empty_source_honest_failure():
    env = os.environ.copy()
    env["SOURCE_CHANNELS"] = ""
    result = _run_launcher(["run", "--non-interactive"], env=env)
    assert result.returncode == 1, (
        f"empty SOURCE_CHANNELS must fail honestly, got {result.returncode}: "
        f"{result.stderr[:500]}{result.stdout[:500]}"
    )


def test_launcher_schedule_empty_source_fails():
    env = os.environ.copy()
    env["SOURCE_CHANNELS"] = ""
    result = _run_launcher(["run", "--schedule", "--non-interactive"], env=env)
    assert result.returncode == 1


def test_launcher_non_interactive_requires_honest_nonzero():
    env = os.environ.copy()
    env["SOURCE_CHANNELS"] = ""
    result = _run_launcher(["run"], env=env, stdin=subprocess.DEVNULL)
    assert result.returncode != 0


def test_launcher_install_termux_script_copies_launcher():
    text = (ROOT / "scripts" / "install_termux.sh").read_text(encoding="utf-8")
    assert "yasinrelay-termux" in text
    assert ".venv/bin/yasinrelay-termux" in text
    assert "scripts/yasinrelay-termux" in text


def test_launcher_no_shell_injection_surface():
    text = LAUNCHER_SRC.read_text(encoding="utf-8")
    assert "eval " not in text
    assert '"$@"' in text


def test_launcher_ld_preload_composition_no_duplicate():
    text = LAUNCHER_SRC.read_text(encoding="utf-8")
    assert 'case ":${LD_PRELOAD}:"' in text
    env = os.environ.copy()
    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}"
    prefix = env.get("PREFIX", "/data/data/com.termux/files/usr")
    env["LD_PRELOAD"] = f"{prefix}/lib/libpython{py_ver}.so"
    result = _run_launcher(["--help"], env=env)
    assert result.returncode == 0, result.stderr


def test_launcher_installed_exists_and_executable():
    if not LAUNCHER.exists():
        assert LAUNCHER_SRC.exists()
        return
    mode = LAUNCHER.stat().st_mode
    assert mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    text = LAUNCHER.read_text(encoding="utf-8")
    assert "bash" in text.splitlines()[0]
