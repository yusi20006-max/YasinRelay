# Git History Secret Cleanup Guide — YasinRelay

**Status:** Controlled rewrite workflow prepared (not yet executed).  
**Date:** 2026-08-08  
**Scope:** Security / history hygiene only. No application or fetcher changes.

---

## 1. Why cleanup is necessary

A file named `.env` containing an Eitaa API token was previously committed.

- The exposed token has already been **revoked / rotated**.
- Residual risk is historical: anyone with the Git history can still recover the old value.
- Detection (workflow run on 2026-08-08) confirmed:

| Check | Result |
|-------|--------|
| Tracked `.env` (HEAD) | **FOUND** |
| Historical `.env` paths | **FOUND** (count=3) |
| Historical `EITAA_TOKEN` string | **FOUND** → REDACTED |
| `.gitignore` protects `.env` / `.env.*` | **FOUND** |
| Main SHA at detection | `4c04e43c0945dc722c4e1c8431c22fdf6b824c79` |

No secret values were printed during detection.

---

## 2. Primary cleanup strategy

The known secret lived in the tracked file `.env`.

Therefore the **primary and correct** rewrite action is:

```bash
git filter-repo --path .env --invert-paths --quiet
```

This removes the path `.env` from every historical commit.

Do **not** use a key-name replacement such as `EITAA_TOKEN==>REDACTED`.
That leaves the actual token value intact and is insufficient.

After path removal, presence-only scans for `EITAA_TOKEN` and broader credential-like patterns are required.
If anything remains, the workflow stops with:

```text
POTENTIAL_REMAINING_CREDENTIAL: REDACTED
```

and requires a separate deliberate cleanup step. No guessed replacement is applied.

---

## 3. Workflow behaviour

File: `.github/workflows/git-history-secret-cleanup.yml`

### Mode: `detect` (default)

- Non-destructive
- Permissions: `contents: read`
- Reports only FOUND / NOT_FOUND / REDACTED
- Includes current-tree presence-only credential pattern scan

### Mode: `rewrite`

Runs only when **all** of the following are true:

1. `mode` = `rewrite`
2. `confirmation` = exactly `REMOVE-HISTORICAL-SECRETS`
3. Repository identity = `yusi20006-max/YasinRelay`
4. `expected_sha` is non-empty and equals current HEAD SHA

Then it will:

1. Create and push a safety backup tag: `backup/pre-secret-cleanup-YYYYMMDD-HHMMSS`
2. Run quiet `git filter-repo --path .env --invert-paths`
3. Verify `.env` is gone from the working tree and from history
4. Verify `.gitignore` still protects `.env`
5. Presence-only re-scan for `EITAA_TOKEN`
6. Presence-only current-tree credential pattern scan
7. If residual found → fail with `POTENTIAL_REMAINING_CREDENTIAL: REDACTED`
8. Push cleaned history to branch **`security/history-cleaned`** using `--force-with-lease` only

**This workflow never force-pushes `main`.**

---

## 4. How to run detection (safe)

1. Actions → **Git History Secret Cleanup (Controlled)**
2. Run workflow
3. `mode` = `detect`
4. Leave confirmation empty
5. `expected_sha` may be left empty in detect mode
6. Review logs (FOUND / NOT_FOUND / REDACTED only)

---

## 5. How to run the controlled rewrite (after this PR is merged)

1. Ensure collaborators are notified that history will change.
2. Note the current main SHA (required).
3. Actions → **Git History Secret Cleanup (Controlled)** → Run workflow
4. Set:
   - `mode` = `rewrite`
   - `confirmation` = `REMOVE-HISTORICAL-SECRETS`
   - `expected_sha` = current main SHA (**required**)
5. Wait for success.
6. Confirm:
   - Backup tag exists
   - Branch `security/history-cleaned` exists and looks correct
7. **Maintainer-only force-push to main** (from a trusted machine):

```bash
git fetch origin
git checkout security/history-cleaned
# Review carefully
git push --force-with-lease origin security/history-cleaned:main
```

Prefer `--force-with-lease` over bare `--force`.

---

## 6. Backup / reference procedure

Before any rewrite the workflow creates:

```text
backup/pre-secret-cleanup-YYYYMMDD-HHMMSS
```

The tag message includes the pre-rewrite SHA.

Additionally, maintainers should keep an offline mirror:

```bash
git clone --mirror https://github.com/yusi20006-max/YasinRelay.git YasinRelay-backup.git
```

---

## 7. Verification checklist (after rewrite + force-push to main)

- [ ] `git log --all --full-history -- .env` returns nothing
- [ ] Presence-only scan for `EITAA_TOKEN` returns NOT_FOUND
- [ ] Current-tree credential pattern scan returns NOT_FOUND
- [ ] `git ls-files .env` shows not tracked
- [ ] `.gitignore` still lists `.env` and `.env.*`
- [ ] `.env.example` (if present) contains only placeholders
- [ ] Detection workflow run on new main reports clean results
- [ ] No real token appears in any file or log

---

## 8. Impact on existing clones

After main is force-pushed, all existing clones diverge.

Collaborators must either re-clone or:

```bash
git fetch origin
git checkout main
git reset --hard origin/main
```

Communicate this clearly **before** the force-push.

---

## 9. Related work (out of scope)

- Fetcher / Go binary / test failures → **YasinRelay #35**
- Application logic changes → separate issues

This workflow and document contain **no application or fetcher changes**.

---

## 10. Ownership

Only repository maintainers should:

1. Run mode=rewrite with the confirmation string and correct `expected_sha`
2. Force-push cleaned history to main
3. Notify collaborators

Always prefer a second human review before force-pushing rewritten history.
