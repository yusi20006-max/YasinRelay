from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "install_termux.sh"


def test_termux_bootstrap_contract() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert "set -euo pipefail" in text
    assert "pkg install -y python git clang make pkg-config openssl openssl-tool libffi cmake patchelf golang" in text
    assert 'PYTHON_BIN="${PREFIX}/bin/python"' in text
    assert 'GO_BIN="${PREFIX}/bin/go"' in text
    assert '"${PYTHON_BIN}" -m venv .venv' in text
    assert "python -m pip install -e ." in text
    assert "go test ./..." in text
    assert "go build -o openfeed-fetch main.go" in text
    assert "python -m pytest -q" in text
    assert "python -m yasinrelay.cli --help" in text


def test_termux_bootstrap_is_termux_only() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert '"${PREFIX:-}" != "/data/data/com.termux/files/usr"' in text
