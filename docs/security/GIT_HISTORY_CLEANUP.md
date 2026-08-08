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

### 4.3 Recommended local rewrite (example)

> Perform this on a **temporary clone**, never on your only copy of the repository.

```bash
git clone https://github.com/yusi20006-max/YasinRelay.git YasinRelay-cleanup
cd YasinRelay-cleanup

# Install tool
pip install git-filter-repo

# Remove .env from every commit
git filter-repo --path .env --invert-paths

# Optionally replace known token strings with a placeholder
# (use a file; do not put the real token on the command line in shared logs)
# printf 'OLD_TOKEN_PLACEHOLDER==>REDACTED\n' > /tmp/replacements.txt
# git filter-repo --replace-text /tmp/replacements.txt

# Verify
git log --all --full-history -- .env   # should show nothing
git grep -I EITAA_TOKEN $(git rev-list --all) || echo "clean"
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
- [ ] `git grep -I EITAA_TOKEN $(git rev-list --all)` returns nothing
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
