# fetcher/

Vendored OpenFeed-based Telegram fetch path (TeleMirror → Google → GoogleTranslate → Direct).

## Build

From repository root:

```bash
./scripts/build-fetcher.sh
# or:
cd fetcher && go build -o openfeed-fetch .
```

Requires **Go 1.25+**. The binary `fetcher/openfeed-fetch` is gitignored; CI builds it before the test suite (see `.github/workflows/fetcher-e2e.yml`).

## CLI contract

```
openfeed-fetch fetch --channel <channel> --limit <n>
```

Stdout JSON:

```json
[
  {"message_id": "123", "text": "...", "media_url": "https://..."},
  ...
]
```

## Local development without Go

- Unit / pipeline tests can use `FakeFetcher`.
- E2E tests mock `subprocess.run` and auto-create a throwaway stub binary when the real binary is absent.
- Production and full integration require a real `go build`.
