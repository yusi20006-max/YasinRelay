from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "install_termux.sh"
PYPROJECT = ROOT / "pyproject.toml"


def test_termux_bootstrap_contract() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert "set -euo pipefail" in text
    assert "pkg install -y python git clang make pkg-config openssl openssl-tool libffi cmake patchelf golang" in text
    assert "ANDROID_API_LEVEL" in text
    assert 'PYTHON_BIN="${PREFIX}/bin/python"' in text
    assert 'GO_BIN="${PREFIX}/bin/go"' in text
    assert '"${PYTHON_BIN}" -m venv .venv' in text
    assert "python -m pip install -e ." in text
    assert 'git clone --depth 1 https://github.com/yusi20006-max/Yasin-AI.git "${YASIN_AI_DIR}"' in text
    assert 'python -m pip install -e "${YASIN_AI_DIR}"' in text
    assert "cp .env.example .env" in text
    assert "go test ./..." in text
    assert "go build -o openfeed-fetch main.go" in text
    assert "python -m pytest -q" in text
    assert "python -m yasinrelay.cli --help" in text
    assert "Yasin-AI public contracts: OK" in text
    assert "YasinAIContentProcessor" in text
    assert "PassthroughProcessor" in text


def test_termux_bootstrap_is_termux_only() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert '"${PREFIX:-}" != "/data/data/com.termux/files/usr"' in text


def test_yasin_ai_is_not_a_pypi_dependency() -> None:
    text = PYPROJECT.read_text(encoding="utf-8")
    assert '"yasinai>=1.1.4"' not in text


def test_noninteractive_cli_fails_without_tty_when_interactive_requested(monkeypatch) -> None:
    from yasinrelay.cli import main

    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    # Interactive run (without --non-interactive and without --channel) without TTY should fail cleanly with code 2
    code = main(["run"])
    assert code == 2


def test_process_lifecycle_and_noninteractive_execution(tmp_path, monkeypatch) -> None:
    import os
    import signal
    import subprocess
    import sys
    import time

    env = os.environ.copy()
    env["EITAA_TOKEN"] = "fake_token"
    env["EITAA_CHANNEL"] = "@dest_channel"
    env["SOURCE_CHANNELS"] = "@source_channel"
    env["AI_PROVIDER"] = "passthrough"
    env["SCHEDULE_INTERVAL"] = "1"
    env["DATABASE_PATH"] = str(tmp_path / "test_lifecycle.db")

    cmd = [
        sys.executable,
        "-m",
        "yasinrelay.cli",
        "run",
        "--schedule",
        "--non-interactive",
    ]

    proc = subprocess.Popen(
        cmd,
        cwd=str(ROOT),
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    try:
        assert proc.pid > 0, "Service process should start and have a valid PID"
        time.sleep(0.5)
        assert proc.poll() is None, "Service process should remain running in scheduled mode"

        # Terminate cleanly with SIGINT
        proc.send_signal(signal.SIGINT)
        out, err = proc.communicate(timeout=5)
        assert proc.returncode in (0, 130, -signal.SIGINT), f"Process exited with {proc.returncode}"
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()
