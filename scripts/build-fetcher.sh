#!/usr/bin/env bash
# Build the vendored OpenFeed Go fetcher binary used by SubprocessFetcher.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT/fetcher"
if ! command -v go >/dev/null 2>&1; then
  echo "ERROR: go toolchain not found. Install Go 1.25+ to build openfeed-fetch." >&2
  exit 1
fi
go build -o openfeed-fetch .
test -x openfeed-fetch
echo "Built: $ROOT/fetcher/openfeed-fetch"
