# Git History Secret Cleanup Guide — YasinRelay

**Status:** Controlled rewrite workflow executed; cleaned history on `security/history-cleaned`.  
**Latest rewrite date:** 2026-08-16  
**Scope:** Security / history hygiene only. No application or fetcher changes.

---

## 1. Why cleanup is necessary

A file named `.env` containing an Eitaa API token was previously committed.

- The exposed token has already been **revoked / rotated**.
- Residual risk is historical: anyone with the uncleaned Git history can still recover the old value.
- Detection confirmed historical `.env` path presence on `main` (values never printed in logs/docs).

---

## 2. Primary cleanup strategy

The known secret lived in the tracked file `.env`.

Primary rewrite action:

```bash
git filter-repo --path .env --invert-paths --quiet
```

Do **not** replace only a variable *name* with a placeholder. That leaves real values intact.

After path removal, presence-only scans run again. Matches that appear **only** in trusted scanner/documentation paths are treated as false positives (the workflow and this document legally mention the variable name as a scan pattern). Matches **outside** those paths fail closed:

```text
POTENTIAL_REMAINING_CREDENTIAL: REDACTED
```

Trusted false-positive exclusion paths:

- `.github/workflows/git-history-secret-cleanup.yml`
- `docs/security/GIT_HISTORY_CLEANUP.md`

---

## 3. Workflow behaviour

File: `.github/workflows/git-history-secret-cleanup.yml`

### Mode: `detect` (default)

- Non-destructive; `contents: read`
- Reports only FOUND / NOT_FOUND / REDACTED
- Path-aware token/credential pattern scan (trusted scanner/docs excluded)

### Mode: `rewrite`

Requires all of:

1. `mode` = `rewrite`
2. `confirmation` = exactly `REMOVE-HISTORICAL-SECRETS`
3. Repository = `yusi20006-max/YasinRelay`
4. `expected_sha` non-empty and equal to current HEAD

Then:

1. Safety backup tag
2. Quiet `git filter-repo --path .env --invert-paths`
3. Verify `.env` gone from tree and history
4. Verify `.gitignore` still protects `.env`
5. Path-aware residual pattern scan (fail-closed outside trusted paths)
6. Push cleaned history only to `security/history-cleaned` via `--force-with-lease`

**Never force-pushes `main`.**

---

## 4. How to run detection

1. Actions → **Git History Secret Cleanup (Controlled)**
2. `mode` = `detect`
3. Leave confirmation / expected_sha empty
4. Review FOUND / NOT_FOUND / REDACTED only

---

## 5. Rewrite execution log

### 2026-08-08

- Workflow runs completed with rewrite gates.
- Backup tags created (examples):
  - `backup/pre-secret-cleanup-20260808-123802`
  - `backup/pre-secret-cleanup-20260808-155915`
- Cleaned tip at that time was documented as `4d9c3f69a0c1da27adb023d2362a2f6ff83b1fcd`.

### 2026-08-16 (Issue #34 continuation)

- Re-ran controlled rewrite from then-current `main` HEAD `a4f1d4cedb827c7efb5a1977e2885e64b0f6bdf6` (includes Yasin-AI #43 migration).
- Workflow run: [31932727003](https://github.com/yusi20006-max/YasinRelay/actions/runs/31932727003) — **success**.
- Verified:
  - `git log security/history-cleaned -- .env` → **empty**
  - `git log origin/main -- .env` → still lists historical path commits (expected until main promotion)
  - `.gitignore` still ignores `.env` / `.env.*` with `!.env.example`
  - Tip of cleaned branch: `9f53282873a57053a015c0870aeccfc05414038a` (rewritten equivalent of post-#43 main)

### Maintainer-only final step

Promote cleaned history to `main` **only** from a trusted machine after coordinating with collaborators:

```bash
git fetch origin
git checkout security/history-cleaned
git push --force-with-lease origin security/history-cleaned:main
```

After promotion, collaborators must re-clone or hard-reset local clones.

---

## 6. Verification checklist (after maintainer force-push)

- [ ] `git log --all --full-history -- .env` empty
- [ ] No non-trusted residual pattern matches
- [ ] `.env` not tracked
- [ ] `.gitignore` still lists `.env` / `.env.*`
- [ ] Collaborators re-cloned or hard-reset

---

## 7. Related work (out of scope)

- Fetcher / tests → **YasinRelay #35**
- Application logic → separate issues

No application or fetcher changes in this workflow/docs.
