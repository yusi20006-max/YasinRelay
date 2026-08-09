# Git History Secret Cleanup Guide — YasinRelay

**Status:** Controlled rewrite workflow already executed.
**Date:** 2026-08-08  
**Scope:** Security / history hygiene only. No application or fetcher changes.

---

## 1. Why cleanup is necessary

A file named `.env` containing an Eitaa API token was previously committed.

- The exposed token has already been **revoked / rotated**.
- Residual risk is historical: anyone with the Git history can still recover the old value.
- Detection confirmed tracked and historical `.env` presence (values never printed).

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

## 5. How to run controlled rewrite (already executed)

The controlled rewrite workflow has already been successfully executed.

During the execution:
- Repository collaborators were notified.
- The workflow ran with `mode` = `rewrite`, `confirmation` = `REMOVE-HISTORICAL-SECRETS`.
- Safety backup tags were created:
  - `backup/pre-secret-cleanup-20260808-123802`
  - `backup/pre-secret-cleanup-20260808-155915`
- The quiet `git filter-repo --path .env --invert-paths` was completed.
- Verification was done ensuring `.env` is fully removed from tree and history, and `.gitignore` still protects it.
- The clean branch `security/history-cleaned` is available with HEAD SHA `4d9c3f69a0c1da27adb023d2362a2f6ff83b1fcd`.

The final migration step to force-push the cleaned branch to `main` remains to be executed by the Maintainer using `--force-with-lease` from a trusted machine:

```bash
git fetch origin
git checkout security/history-cleaned
git push --force-with-lease origin security/history-cleaned:main
```

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
