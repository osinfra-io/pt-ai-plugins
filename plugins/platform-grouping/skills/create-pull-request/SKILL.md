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
gh pr create --draft --title "<sentence-case title>" --body "<what changed and why>"
```

Always open PRs as **draft**. When the user says "ready for review", mark it ready:

```bash
gh pr ready
```

## 5. Label the pull request

Apply one or more labels that best describe what the PR touches:

| Label | Use for |
|---|---|
| `actions` | GitHub Actions workflows and automation |
| `copilot` | Copilot instructions, skills, hooks, and agents |
| `dependencies` | Updates to a dependency file |
| `devex` | Developer experience, tooling, and local environment |
| `docker` | Docker images and container configuration |
| `docs` | Docusaurus documentation site or other markdown documentation |
| `kubernetes` | Kubernetes manifests, Helm charts, and cluster configuration |
| `misc` | Miscellaneous work that does not fit another label |
| `observability` | Observability, monitoring, and alerting |
| `opentofu` | OpenTofu infrastructure code |
| `scripts` | Generator and utility scripts |
| `security` | Driven by security requirements or hardening |
| `tests` | Test coverage, test infrastructure, and evaluations |

```bash
gh pr edit --add-label <label>
```

## 6. After approval

- **Squash and merge** — every PR lands as a single commit on `main`.
- **Delete the branch** locally and remotely after merging.

```bash
gh pr merge --squash --delete-branch
```
