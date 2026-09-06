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

## Security synchronization (Openfeed Issue #3)

`fetcher/telemirror/security.go` and `fetcher/telemirror/security_test.go`
are kept behaviorally identical to Openfeed's
`internal/telemirror/security.go` / `security_test.go`, and the
`dialTLSFor` direct-dial hardening in `fetcher/telemirror/client.go`
mirrors Openfeed's `internal/telemirror/client.go`:

- DNS-rebinding TOCTOU pinning: the direct path (`ap.ip == ""`) resolves
  and validates inside the dial closure via `resolveValidatedIPs` and
  dials only validated IP literals — the hostname is never passed to
  `net.Dialer`. Fail closed on loopback, private, link-local, ULA,
  unspecified, multicast, or mixed DNS answers.
- `validateSafeURL` (check-time gate) + `safeCheckRedirect` (redirect
  re-validation) are shared semantics in both copies.
- Fixed-IP fronted attempts (`ap.ip != ""`) are preserved unchanged.

Any security change to either copy must be ported to the other so both
implementations stay behaviorally equivalent.
