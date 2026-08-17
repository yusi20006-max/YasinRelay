#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

# YasinRelay Termux/Android first-class bootstrap.

if [ "${PREFIX:-}" != "/data/data/com.termux/files/usr" ]; then
  echo "ERROR: this installer must run inside Termux." >&2
  exit 1
fi

pkg update -y
pkg upgrade -y
pkg install -y python git clang make pkg-config openssl openssl-tool libffi cmake patchelf go

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
PY

python -m pytest -q
python -m yasinrelay.cli --help

# No network credentials are required for the smoke test.
python -m yasinrelay.cli run --channel "@__termux_smoke_test__" --limit 1 || test $? -eq 1

printf '%s\n' \
  'YasinRelay Termux installation completed successfully.' \
  'Activate: source .venv/bin/activate' \
  'CLI: python -m yasinrelay.cli --help' \
  'Single run: python -m yasinrelay.cli run' \
  'Scheduled: python -m yasinrelay.cli run --schedule' \
  'Continuous: python -m yasinrelay.cli run --loop'
