---
name: release-arche-modules
description: Walk the full pt-arche-* dependency chain in release order — detect what needs releasing, tag pt-arche-core-helpers, update SHA pins in all Tier 2 modules, optionally propagate to pt-corpus and pt-pneuma — fully autonomously. Use when asked to release or update arche modules.
---

# Release arche modules

Execute the full arche module release chain autonomously. Do not pause between steps — work through the entire procedure and report a summary at the end.

## Dependency chain

```text
pt-arche-core-helpers                      ← Tier 1 (must release first)
    └── pt-arche-datadog-google-integration
    └── pt-arche-google-cloud-sql
    └── pt-arche-google-kubernetes-engine
    └── pt-arche-google-network
    └── pt-arche-google-project
    └── pt-arche-google-storage-bucket
    └── pt-arche-kubernetes-cert-manager
    └── pt-arche-kubernetes-datadog-operator
    └── pt-arche-kubernetes-istio
    └── pt-arche-kubernetes-opa-gatekeeper  ← Tier 2 (parallel-safe, after Tier 1)
        └── pt-corpus
        └── pt-pneuma                       ← Tier 3 (consumers, optional)
```

## Step 1 — Detect what needs releasing

For each repo in the chain, get the latest release and compare its publish date against recently merged PRs:

```bash
gh release view --repo osinfra-io/pt-arche-core-helpers --json tagName,publishedAt
gh pr list --repo osinfra-io/pt-arche-core-helpers --state merged \
  --json number,title,mergedAt

gh release view --repo osinfra-io/pt-arche-datadog-google-integration --json tagName,publishedAt
gh pr list --repo osinfra-io/pt-arche-datadog-google-integration --state merged \
  --json number,title,mergedAt

# Repeat for each remaining Tier 2 repo:
# pt-arche-google-cloud-sql
# pt-arche-google-kubernetes-engine
# pt-arche-google-network
# pt-arche-google-project
# pt-arche-google-storage-bucket
# pt-arche-kubernetes-cert-manager
# pt-arche-kubernetes-datadog-operator
# pt-arche-kubernetes-istio
# pt-arche-kubernetes-opa-gatekeeper
```

A repo needs a new release if any PR merged **after** the latest release's `publishedAt`.

Determine the next version for each repo using [Semantic Versioning](https://semver.org/):

- PATCH — bug fixes, dependency bumps, documentation tweaks
- MINOR — new resources, new variables, backwards-compatible additions
- MAJOR — breaking changes (removed variables, renamed outputs, incompatible defaults)

## Step 2 — Release pt-arche-core-helpers (Tier 1, if needed)

Get the current tip of `main` and tag it:

```bash
cd pt-arche-core-helpers
git fetch origin main
git log origin/main --oneline -1
git tag vX.Y.Z <sha>
git push origin vX.Y.Z
```

Record the post-merge SHA. This is the `<sha>` used in the tag command — it is the commit already on `main`, so no PR is needed.

If `pt-arche-core-helpers` does not need a release, use the SHA of its current `main` tip as the reference SHA for Tier 2 updates only if any Tier 2 module's `helpers.tofu` is not already pinned to that SHA.

## Step 3 — Release Tier 2 modules (parallel-safe)

For each Tier 2 module that needs a release, execute the following steps. These modules are independent of each other and can be processed in any order (or in parallel).

For each module, replace `<module>` with the repo name (e.g. `pt-arche-google-project`), `<core-sha>` with the 40-character post-merge SHA from Step 2, and `<core-version>` with the new `pt-arche-core-helpers` version tag:

```bash
cd <module>
git checkout main && git pull
git checkout -b update-core-helpers-to-<core-version>
```

Edit `helpers.tofu` — update the `ref=` value to the new core-helpers SHA and inline version comment:

```hcl
source = "github.com/osinfra-io/pt-arche-core-helpers//child?ref=<core-sha>"  # <core-version>
```

Run pre-commit before committing:

```bash
pre-commit autoupdate --freeze && pre-commit run -a
```

Commit, push, open PR, label, and squash-merge:

```bash
git add helpers.tofu
git commit -m "Update pt-arche-core-helpers to <core-version>" \
  -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
git push -u origin update-core-helpers-to-<core-version>
gh pr create \
  --title "Update pt-arche-core-helpers to <core-version>" \
  --body "Bumps the pt-arche-core-helpers SHA pin to <core-version>."
gh pr edit --add-label chore
gh pr merge --squash --delete-branch --auto
```

Wait for the merge to complete, then fetch the post-merge SHA from `main` and tag the new release:

```bash
git checkout main && git pull
git log --oneline -1
git tag vA.B.C <post-merge-sha>
git push origin vA.B.C
```

Record each module's post-merge SHA and new version tag for use in Step 4.

## Step 4 — Update Tier 3 consumers (optional)

**Ask the user before proceeding:**

> Tier 2 modules have been released. Would you like me to also update the Tier 3 consumers (`pt-corpus` and `pt-pneuma`) with the new module SHAs?

If the user confirms, proceed for each consumer. Both `pt-corpus` and `pt-pneuma` may reference Tier 2 modules in `main.tofu` and a core-helpers reference in `helpers.tofu`. Update all `ref=` values that have changed.

For `pt-corpus`:

```bash
cd pt-corpus
git checkout main && git pull
git checkout -b update-arche-modules-YYYYMMDD
```

In `main.tofu`, update every `ref=` for changed Tier 2 modules to their new post-merge SHAs and inline version comments:

```hcl
source = "github.com/osinfra-io/pt-arche-google-project?ref=<new-sha>"  # <new-version>
```

In `helpers.tofu`, if the `pt-arche-core-helpers` `ref=` has changed, update it:

```hcl
source = "github.com/osinfra-io/pt-arche-core-helpers//root?ref=<core-sha>"  # <core-version>
```

Run pre-commit, commit, push, open PR, label, and squash-merge:

```bash
pre-commit autoupdate --freeze && pre-commit run -a
git add main.tofu helpers.tofu
git commit -m "Update arche modules to latest releases" \
  -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
git push -u origin update-arche-modules-YYYYMMDD
gh pr create \
  --title "Update arche modules to latest releases" \
  --body "$(printf 'Bumps arche module SHA pins to their latest releases:\n\n- pt-arche-core-helpers: <core-version>\n- pt-arche-google-project: <version>\n...')"
gh pr edit --add-label chore
gh pr merge --squash --delete-branch --auto
```

Repeat the same process for `pt-pneuma`, updating any modules it references.

## Step 5 — Report

Summarise what was done:

| Repo | Previous | New | PR |
|---|---|---|---|
| pt-arche-core-helpers | vOLD | vNEW | — |
| pt-arche-datadog-google-integration | vOLD | vNEW | #PR |
| pt-arche-google-cloud-sql | vOLD | vNEW | #PR |
| pt-arche-google-kubernetes-engine | vOLD | vNEW | #PR |
| pt-arche-google-network | vOLD | vNEW | #PR |
| pt-arche-google-project | vOLD | vNEW | #PR |
| pt-arche-google-storage-bucket | vOLD | vNEW | #PR |
| pt-arche-kubernetes-cert-manager | vOLD | vNEW | #PR |
| pt-arche-kubernetes-datadog-operator | vOLD | vNEW | #PR |
| pt-arche-kubernetes-istio | vOLD | vNEW | #PR |
| pt-arche-kubernetes-opa-gatekeeper | vOLD | vNEW | #PR |
| pt-corpus | vOLD | — (updated) | #PR |
| pt-pneuma | vOLD | — (updated) | #PR |

Include the PR URL for any PR that was opened. Mark rows skipped (no changes) with "–".
