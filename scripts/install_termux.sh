#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

# YasinRelay Termux/Android first-class bootstrap.

if [ "${PREFIX:-}" != "/data/data/com.termux/files/usr" ]; then
  echo "ERROR: this installer must run inside Termux." >&2
  exit 1
fi

pkg update -y
pkg upgrade -y
# Termux names the Go toolchain package `golang` (not `go`).
pkg install -y python git clang make pkg-config openssl openssl-tool libffi cmake patchelf golang

PYTHON_BIN="${PREFIX}/bin/python"
GO_BIN="${PREFIX}/bin/go"
"${PYTHON_BIN}" --version
"${GO_BIN}" version

rm -rf .venv
"${PYTHON_BIN}" -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip setuptools wheel
python -m pip install -e .
python -m pip install "pytest>=7.4,<10"

# Yasin-AI is a sibling canonical platform, not a PyPI dependency.
# On a fresh Termux installation, bootstrap it automatically beside YasinRelay.
YASIN_AI_DIR="../Yasin-AI"
if [ ! -d "${YASIN_AI_DIR}" ]; then
  git clone --depth 1 https://github.com/yusi20006-max/Yasin-AI.git "${YASIN_AI_DIR}"
fi
if [ ! -f "${YASIN_AI_DIR}/pyproject.toml" ]; then
  echo "ERROR: Yasin-AI checkout is incomplete: ${YASIN_AI_DIR}" >&2
  exit 1
fi
python -m pip install -e "${YASIN_AI_DIR}"

# Create an operator-owned environment file on first install. Never overwrite
# an existing .env and never invent credentials.
if [ ! -f .env ] && [ -f .env.example ]; then
  cp .env.example .env
fi

# Build the Telegram collector using the Termux-native Go toolchain.
(
  cd fetcher
  go mod download
  go test ./...
  go build -o openfeed-fetch main.go
)

python - <<'PY'
import importlib.metadata as metadata
import sys
import yasinrelay

print(f"Python: {sys.version}")
print(f"YasinRelay: {metadata.version('yasin-relay')}")
print(f"YasinRelay import: OK ({yasinrelay.__file__})")

try:
    import yasinai
    from yasinai.contracts import GenerationRequest
    from yasinai.services import GenerationService
    print(f"Yasin-AI: {getattr(yasinai, '__version__', metadata.version('yasinai'))}")
    print("Yasin-AI public contracts: OK")
except ImportError as exc:
    raise SystemExit(f"Yasin-AI public contracts unavailable: {exc}")
PY

# Install canonical Termux launcher
if [ -f scripts/yasinrelay-termux ]; then
  install -m 755 scripts/yasinrelay-termux .venv/bin/yasinrelay-termux
  echo "Installed canonical launcher: .venv/bin/yasinrelay-termux"
fi

python -m pytest -q
python -m yasinrelay.cli --help
.venv/bin/yasinrelay-termux --help

# No network credentials are required for the smoke test.
python -m yasinrelay.cli run --channel "@__termux_smoke_test__" --limit 1 || test $? -eq 1
.venv/bin/yasinrelay-termux run --channel "@__termux_smoke_test__" --limit 1 || test $? -eq 1

printf '%s\n' \
  'YasinRelay Termux installation completed successfully.' \
  'Activate: source .venv/bin/activate' \
  'Config: edit .env before real publishing' \
  'CLI: python -m yasinrelay.cli --help' \
  'Canonical: .venv/bin/yasinrelay-termux run --schedule --non-interactive' \
  'Single run: python -m yasinrelay.cli run --channel @channel' \
  'Scheduled: python -m yasinrelay.cli run --schedule' \
  'Continuous: python -m yasinrelay.cli run --loop'
