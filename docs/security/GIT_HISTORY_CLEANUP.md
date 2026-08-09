# Git History Secret Cleanup Guide — YasinRelay

**Status:** Controlled rewrite workflow successfully executed and verified. Cleaned branch is prepared and awaiting final migration to main.
**Date:** 2026-08-09
**Scope:** Security / history hygiene only. No application or fetcher changes.

---

## 1. Why cleanup is necessary

A file named `.env` containing an Eitaa API token was previously committed.

- The exposed token has already been **revoked / rotated**.
- Residual risk is historical: anyone with the Git history can still recover the old value.
- Detection confirmed tracked and historical `.env` presence (values never printed).

---

## 2. Primary cleanup strategy & Execution State

The known secret lived in the tracked file `.env`.

The primary rewrite action was successfully performed:

```bash
git filter-repo --path .env --invert-paths --quiet
```

### Execution Details:
- **Rewrite Status:** Completed.
- **Cleaned Branch:** `security/history-cleaned`
- **Cleaned Branch Head SHA:** `4d9c3f69a0c1da27adb023d2362a2f6ff83b1fcd`
- **Backup Tag:** `backup/pre-final-migration-20260809` (pointing exactly to the current `main` tip at SHA `7eb28f61ce804f7301676153abccbdb9a2a92e9a`).

After path removal, presence-only scans were re-run. Matches that appear **only** in trusted scanner/documentation paths are treated as false positives (the workflow and this document legally mention the variable name as a scan pattern). Matches **outside** those paths fail closed.

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

## 5. Final Migration and Verification Steps (Remaining)

Once the rewrite is executed and available on `security/history-cleaned`, the maintainer should perform the final migration from a trusted machine:

1. Notify collaborators.
2. Ensure the backup tag `backup/pre-final-migration-20260809` is pushed and verified.
3. Fetch and checkout the cleaned branch:
   ```bash
   git fetch origin
   git checkout security/history-cleaned
   ```
4. Perform the final migration to update the `main` branch:
   ```bash
   git push origin security/history-cleaned:main --force-with-lease
   ```
5. Notify all collaborators to re-clone the repository or perform a hard reset to synchronize with the clean history.

---

## 6. Verification checklist (after final migration)

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
