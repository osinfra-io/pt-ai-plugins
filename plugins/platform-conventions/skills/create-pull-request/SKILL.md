---
name: create-pull-request
description: Create a pull request following osinfra-io platform conventions. Use when asked to open, raise, submit, or put up a pull request (PR) in any osinfra-io repository.
---

# Create a pull request

Follow this procedure to land changes as a pull request using
[GitHub Flow](https://docs.github.com/en/get-started/using-github/github-flow) and the
osinfra-io platform conventions.

## 1. Branch off `main`

Never commit directly to `main`. If the current branch is `main`, create a short,
descriptively named branch:

```bash
git checkout main && git pull && git checkout -b <branch-name>
```

## 2. Commit

Stage the change and write a **sentence-case** commit message in natural language.

- **Do not** use Conventional Commits prefixes (`feat:`, `fix:`, `chore:`, `refactor:`).
- Include the `Co-authored-by` trailer when Copilot helped author the change.

```bash
git commit -m "Improve metadata validation for GKE handler" \
  -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

✅ `Improve metadata validation for GKE handler`
❌ `feat: add metadata endpoint`

## 3. Push

```bash
git push -u origin <branch-name>
```

## 4. Open the pull request

Write the PR title in the same sentence-case style as the commit message, then open it with
the GitHub CLI:

```bash
gh pr create --title "<sentence-case title>" --body "<what changed and why>"
```

Use a **draft** PR (add `--draft`) for early feedback before the work is complete.

## 5. Label the pull request

Apply exactly one category label:

| Label | Use for |
|---|---|
| `bug` | A fix for incorrect behavior |
| `chore` | Maintenance with no user-facing change |
| `documentation` | Documentation-only changes |
| `enhancement` | New capability or improvement |
| `security` | Security fixes or hardening |
| `tech-debt` | Refactoring or cleanup |

```bash
gh pr edit --add-label <label>
```

## 6. After approval

- **Squash and merge** — every PR lands as a single commit on `main`.
- **Delete the branch** locally and remotely after merging.

```bash
gh pr merge --squash --delete-branch
```
