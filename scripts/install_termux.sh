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

# Ensure Android API Level is available for native dependency builds (Clang / CGo).
if [ -z "${ANDROID_API_LEVEL:-}" ]; then
  if command -v getprop >/dev/null 2>&1; then
    ANDROID_API_LEVEL="$(getprop ro.build.version.sdk || true)"
  fi
fi
if ! [[ "${ANDROID_API_LEVEL:-}" =~ ^[0-9]+$ ]]; then
  echo "ERROR: unable to determine Android API level." >&2
  exit 1
fi
if [ "${ANDROID_API_LEVEL}" -lt 30 ]; then
  echo "ERROR: YasinRelay Termux contract requires Android API >= 30; detected ${ANDROID_API_LEVEL}." >&2
  exit 1
fi
export ANDROID_API_LEVEL
echo "Android API level: ${ANDROID_API_LEVEL}"

PYTHON_BIN="${PREFIX}/bin/python"
GO_BIN="${PREFIX}/bin/go"
"${PYTHON_BIN}" --version
"${GO_BIN}" version

rm -rf .venv
"${PYTHON_BIN}" -m venv .venv
source .venv/bin/activate

# Termux Python 3.14 native extensions such as cryptography may require the
# interpreter shared library to be globally visible at runtime. Keep this
# environment explicit and provide a stable launcher for Control Plane/service use.
PYTHON_LIB="${PREFIX}/lib/libpython$("${PYTHON_BIN}" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")').so"
if [ ! -f "${PYTHON_LIB}" ]; then
  echo "ERROR: required Python shared library not found: ${PYTHON_LIB}" >&2
  exit 1
fi
export LD_PRELOAD="${PYTHON_LIB}${LD_PRELOAD:+:${LD_PRELOAD}}"
echo "LD_PRELOAD: ${LD_PRELOAD}"

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

# Stable non-interactive launcher for Termux services and Control Plane callers.
cat > .venv/bin/yasinrelay-termux <<'LAUNCHER'
#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PREFIX="${PREFIX:-/data/data/com.termux/files/usr}"
PYTHON_BIN="${ROOT}/.venv/bin/python"
PYTHON_LIB="${PREFIX}/lib/libpython$(${PYTHON_BIN} -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")').so"

if [ ! -f "${PYTHON_LIB}" ]; then
  echo "ERROR: Python shared library not found: ${PYTHON_LIB}" >&2
  exit 1
fi

export LD_PRELOAD="${PYTHON_LIB}${LD_PRELOAD:+:${LD_PRELOAD}}"
exec "${PYTHON_BIN}" -m yasinrelay.cli "$@"
LAUNCHER
chmod +x .venv/bin/yasinrelay-termux

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

python -m pytest -q
python -m yasinrelay.cli --help

# Deterministic canonical-contract smoke test. No network or credentials required.
python - <<'SMOKE'
import sys
from types import SimpleNamespace

import yasinrelay
import yasinrelay.yasinai_adapter as adapter
from yasinrelay.ai_processor import PassthroughProcessor
from yasinrelay.fetch_engine import Post

print(f"Executing Termux smoke test on Python {sys.version.split()[0]}...")
assert adapter.is_yasinai_available(), "Canonical Yasin-AI contracts must be importable"

class FakeGenerationService:
    def generate(self, request):
        return SimpleNamespace(
            success=True,
            text=f"[Yasin-AI processed] {request.prompt}",
            error=None,
            model=request.model,
            provider=request.provider or "test",
        )

processor = adapter.build_content_processor(
    ai_provider="yasinai",
    generation_service=FakeGenerationService(),
)
assert isinstance(processor, adapter.YasinAIContentProcessor), (
    f"Expected YasinAIContentProcessor, got {type(processor)}"
)
assert not isinstance(processor, PassthroughProcessor), "Silent fallback to PassthroughProcessor detected!"

item = Post(channel="@__termux_smoke_test__", message_id="1", text="Termux smoke test post content")
res = processor.process(item)
assert res.text == "[Yasin-AI processed] Termux smoke test post content"
print("Canonical adapter smoke test: OK")
SMOKE

# Verify the stable service launcher preserves the native runtime environment.
.venv/bin/yasinrelay-termux --help >/dev/null

printf '%s\n' \
  'YasinRelay Termux installation completed successfully.' \
  'Activate: source .venv/bin/activate' \
  'Service launcher: .venv/bin/yasinrelay-termux run --schedule --non-interactive' \
  'Config: edit .env before real publishing' \
  'CLI: python -m yasinrelay.cli --help' \
  'Single run: python -m yasinrelay.cli run --channel @channel' \
  'Scheduled: python -m yasinrelay.cli run --schedule' \
  'Continuous: python -m yasinrelay.cli run --loop'
