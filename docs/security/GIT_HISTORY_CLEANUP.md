# Git History Secret Cleanup Guide — YasinRelay

**Status:** Preparation only (detection workflow).  
**Date:** 2026-08-08  
**Scope:** Security / history hygiene. Does **not** change application code or the fetcher.

---

## 1. Why this is necessary

A file named `.env` containing an Eitaa API token was previously committed to this repository.

- The exposed token has already been **revoked / rotated**.
- The remaining risk is historical: anyone with access to the Git history can still see the old value.
- Therefore a controlled history rewrite is planned for a later, deliberate step.

This document and the accompanying GitHub Actions workflow prepare that future step safely.

> **Important:** Do **not** run any history rewrite until the detection workflow has been reviewed and a backup strategy is in place.

---

## 2. What has already been done

| Item | Status |
|------|--------|
| Token revoked / rotated | Done |
| `.env` present in current tree | Yes (still tracked) |
| `.gitignore` contains `.env` | Yes |
| Detection workflow added | This PR |
| Actual history rewrite | **Not yet** |

---

## 3. Detection workflow (this PR)

File: `.github/workflows/git-history-secret-cleanup.yml`

- Trigger: **manual only** (`workflow_dispatch`)
- Default mode: `detect` (non-destructive)
- Permissions: `contents: read` only
- Never prints secret values (only `FOUND` / `NOT_FOUND` / `REDACTED`)
- Historical scan uses presence-only methods (`git log -S` / `-G` and discarded `git grep`) so matching content never appears in logs
- Does not rewrite history, does not force-push, does not touch `main`

### How to run detection

1. Go to the repository → **Actions**
2. Select **Git History Secret Cleanup (Controlled)**
3. Click **Run workflow**
4. Leave `mode` = `detect`
5. Leave `confirmation` empty
6. Run and inspect the summary logs

---

## 4. Future rewrite procedure (NOT enabled yet)

When you are ready to remove secrets from history, follow this sequence carefully.

### 4.1 Prerequisites

1. Detection workflow reports the expected findings.
2. A full backup exists (see below).
3. All collaborators are notified that history will change.
4. A follow-up PR deliberately enables the rewrite job (currently hard-disabled with `if: false`).
5. You have a recovery plan for local clones.

### 4.2 Create a safety backup / reference

```bash
# On a clean machine with a full clone
git clone --mirror https://github.com/yusi20006-max/YasinRelay.git YasinRelay-backup.git

# Or create a backup branch/tag on the remote (from a trusted machine)
git checkout main
git tag backup/pre-secret-cleanup-$(date +%Y%m%d)
git push origin backup/pre-secret-cleanup-YYYYMMDD
```

Keep the mirror somewhere safe offline as well.

### 4.3 Recommended local rewrite

> Perform this on a **temporary clone**, never on your only copy of the repository.

**Primary strategy (sufficient for the known leak):**  
The revoked token lived in the tracked file `.env`. Removing that path from every historical commit is therefore the correct and complete first action.

```bash
git clone https://github.com/yusi20006-max/YasinRelay.git YasinRelay-cleanup
cd YasinRelay-cleanup

pip install git-filter-repo

# Primary action — remove .env from all history
git filter-repo --path .env --invert-paths
```

**Residual value scrubbing (only if still needed):**  
If, after path removal, detection still finds the raw token *value* inside other files, scrub those values with a **local, uncommitted** replacements file. The real value must come from a secure source and must **never** be written into the repository, the workflow YAML, documentation, or CI logs.

```bash
# Illustrative only — do not hard-code real secrets
# printf '%s\n' "<VALUE_FROM_SECURE_SOURCE>==>REDACTED" > /tmp/replacements.txt
# git filter-repo --replace-text /tmp/replacements.txt
# shred -u /tmp/replacements.txt
```

> Do **not** replace only the key name `EITAA_TOKEN`. That leaves the actual token value intact and is insufficient.

**Verify:**

```bash
git log --all --full-history -- .env          # should show nothing
# Presence-only check (do not print matching lines):
git log --all --pretty=format:'%H' -S'EITAA_TOKEN' | head -1 || echo "clean"
```

### 4.4 Coordinate the force-push

Only after verification:

```bash
# WARNING: This rewrites public history
git push origin --force --all
git push origin --force --tags
```

Prefer force-pushing a temporary branch first and opening a PR for final review, rather than pushing directly to `main`.

### 4.5 After the rewrite — existing clones

All existing clones will have diverged history. Collaborators should:

```bash
git fetch origin
git checkout main
git reset --hard origin/main   # destructive to local uncommitted work
# or simply re-clone the repository
```

Communicate this clearly before the force-push.

---

## 5. Verification checklist (after future rewrite)

- [ ] `git log --all --full-history -- .env` returns no commits
- [ ] Presence-only scan for `EITAA_TOKEN` returns no commits
- [ ] `.env` is listed in `.gitignore`
- [ ] `.env.example` (if present) contains only placeholders
- [ ] Detection workflow run reports `NOT_FOUND` for historical secrets
- [ ] No real token appears in any remaining file or log

---

## 6. .gitignore guidance

Recommended entries (already partially present):

```
.env
.env.*
!.env.example
```

Do not commit real secrets. Use `.env.example` for documentation of required variables.

---

## 7. Related work (out of scope)

- Fetcher / Go binary stabilization → **YasinRelay #35**
- Application logic, tests, pipeline fixes → separate issues

This document and workflow intentionally contain **no application code changes**.

---

## 8. Contact / ownership

Only repository maintainers should enable or run the destructive phase.
Always prefer a second human review before any force-push of rewritten history.
