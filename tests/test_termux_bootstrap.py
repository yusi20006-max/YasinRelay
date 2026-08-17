from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "install_termux.sh"
PYPROJECT = ROOT / "pyproject.toml"


def test_termux_bootstrap_contract() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert "set -euo pipefail" in text
    assert "pkg install -y python git clang make pkg-config openssl openssl-tool libffi cmake patchelf golang" in text
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


def test_termux_bootstrap_is_termux_only() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert '"${PREFIX:-}" != "/data/data/com.termux/files/usr"' in text


def test_yasin_ai_is_not_a_pypi_dependency() -> None:
    text = PYPROJECT.read_text(encoding="utf-8")
    assert '"yasinai>=1.1.4"' not in text
