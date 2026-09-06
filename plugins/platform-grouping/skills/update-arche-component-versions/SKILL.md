---
name: update-arche-component-versions
description: Check all pt-arche-kubernetes-* modules for outdated upstream component versions (Istio, cert-manager, istio-csr, Datadog Operator, Datadog Agent, OPA Gatekeeper), update the pinned defaults, open one PR per module, merge, and release. Use when asked to update, bump, or check component versions in arche modules.
---

# Update arche component versions

Execute the full component version update autonomously. Do not pause between steps — work through the entire procedure and report a summary at the end.

> **PR conventions:** branch naming, sentence-case titles, no Conventional Commits prefix, the `Co-authored-by` trailer, and the label taxonomy all follow the **create-pull-request** skill — that skill is the single source of truth for those mechanics. The commands below apply the release-specific titles and labels and merge autonomously (`--admin`), unlike the approval-gated flow in create-pull-request.

## Version registry

Each `pt-arche-kubernetes-*` module pins upstream component versions as variable defaults. Use this registry as the source of truth for where each version lives and how to discover the latest release. After collecting the current pinned value and latest upstream value for each row, emit report rows in the shape `Module | Variable | Current | Latest | Needs update?` from the discovered values — do not maintain a second hand-filled comparison table.

| Module | File | Variable | Upstream repo | Version format |
| --- | --- | --- | --- | --- |
| pt-arche-kubernetes-cert-manager | `regional/variables.tofu` | `cert_manager_version` | `cert-manager/cert-manager` | GitHub tag `vX.Y.Z` → strip `v` → `X.Y.Z` |
| pt-arche-kubernetes-cert-manager | `regional/istio-csr/variables.tofu` | `cert_manager_istio_csr_version` | `cert-manager/istio-csr` | GitHub tag `vX.Y.Z` → strip `v` → `X.Y.Z` |
| pt-arche-kubernetes-datadog-operator | `regional/variables.tofu` | `operator_version` | `DataDog/helm-charts` | GitHub tag `datadog-operator-X.Y.Z` → strip prefix → `X.Y.Z` |
| pt-arche-kubernetes-datadog-operator | `regional/manifests/variables.tofu` | `node_agent_tag` | `DataDog/datadog-agent` | GitHub tag `X.Y.Z` (no `v`) |
| pt-arche-kubernetes-datadog-operator | `regional/manifests/variables.tofu` | `cluster_agent_tag` | same as `node_agent_tag` — always the same version | same as `node_agent_tag` |
| pt-arche-kubernetes-istio | `regional/variables.tofu` | `istio_version` | `istio/istio` | GitHub tag `vX.Y.Z` → strip `v` → `X.Y.Z` |
| pt-arche-kubernetes-opa-gatekeeper | `regional/variables.tofu` | `gatekeeper_version` | `open-policy-agent/gatekeeper` | GitHub tag `vX.Y.Z` (keep `v` in variable) |

## Step 1 — Detect current and latest versions

Read the current pinned defaults from each module:

```bash
grep 'default' arche/pt-arche-kubernetes-cert-manager/regional/variables.tofu   arche/pt-arche-kubernetes-cert-manager/regional/istio-csr/variables.tofu   arche/pt-arche-kubernetes-datadog-operator/regional/variables.tofu   arche/pt-arche-kubernetes-datadog-operator/regional/manifests/variables.tofu   arche/pt-arche-kubernetes-istio/regional/variables.tofu   arche/pt-arche-kubernetes-opa-gatekeeper/regional/variables.tofu
```

Fetch the latest upstream release for each component:

```bash
# cert-manager — strip leading 'v'
gh release view --repo cert-manager/cert-manager --json tagName   --jq '.tagName | ltrimstr("v")'

# cert-manager istio-csr — strip leading 'v'
gh release view --repo cert-manager/istio-csr --json tagName   --jq '.tagName | ltrimstr("v")'

# Datadog Operator Helm chart — find latest datadog-operator-* tag and strip prefix
gh release list --repo DataDog/helm-charts --limit 30 --json tagName   --jq '[.[] | .tagName | select(startswith("datadog-operator-"))][0] | sub("^datadog-operator-"; "")'

# Datadog Agent / Cluster Agent — no 'v' prefix in the tag or the variable
# Use the latest stable release (exclude rc, beta, alpha tags)
gh release list --repo DataDog/datadog-agent --limit 10 --json tagName,isPrerelease   --jq '[.[] | select(.isPrerelease == false)][0].tagName'

# Istio — strip leading 'v' for the variable value
gh release view --repo istio/istio --json tagName   --jq '.tagName | ltrimstr("v")'

# OPA Gatekeeper — keep the 'v' prefix in the variable value
gh release view --repo open-policy-agent/gatekeeper --json tagName   --jq '.tagName'
```

If all versions are current, report the computed rows and stop — nothing to do.

## Step 2 — Update modules (one PR per repo)

The four modules are independent and can be processed in any order. For each module that has at least one outdated version variable, follow the procedure below.

Replace `<module>` with the repo name, `<component>` with a short description (for example `istio-1.30.1`), and `<new-version>` with the new version value.

```bash
cd arche/<module>
git checkout main && git pull
git checkout -b update-component-versions
```

Edit the variable file(s) — update only the `default` value(s) that have changed. Do not touch any other lines.

When multiple variables in the same repo need updating (for example both `node_agent_tag` and `cluster_agent_tag` in `pt-arche-kubernetes-datadog-operator`), update all of them in the same branch and commit.

Run pre-commit before committing:

```bash
pre-commit autoupdate --freeze && pre-commit run -a
```

Commit, push, open PR, label, and squash-merge:

```bash
git add -A
git commit -m "Update <component(s)> to <new-version(s)>"   -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
git push -u origin update-component-versions
gh pr create   --title "Update <component(s)> to <new-version(s)>"   --body "<Brief description of what changed. List each bumped variable and its old → new value.>"
gh pr edit --add-label dependencies
gh pr merge --squash --delete-branch --admin
```

Wait for the merge to complete, then fetch the post-merge SHA from `main`:

```bash
git checkout main && git pull
```

### Module-specific notes

**pt-arche-kubernetes-cert-manager**
Both `cert_manager_version` (in `regional/`) and `cert_manager_istio_csr_version` (in `regional/istio-csr/`) live in the same repo — include both in one PR and one commit if both need updating.

**pt-arche-kubernetes-datadog-operator**
Three variables across two files:

- `regional/variables.tofu`: `operator_version`
- `regional/manifests/variables.tofu`: `node_agent_tag` and `cluster_agent_tag`

`node_agent_tag` and `cluster_agent_tag` must always be set to the same version. Include all changed variables in one PR.

## Step 3 — Release updated modules

For each module whose PR was merged in Step 2, determine the next semver and tag:

- PATCH — version-only bump with no API changes (most component updates)
- MINOR — new variable or output added alongside the version bump
- MAJOR — breaking interface change (rare for a version bump)

```bash
cd arche/<module>
MODULE_SHA=$(git rev-parse HEAD)
git tag vA.B.C "$MODULE_SHA"
git push origin vA.B.C
```

The GitHub Actions release workflow generates release notes and publishes automatically.

## Step 4 — Report

Summarise what was done:

| Module | Variable(s) | Old version | New version | PR | Release |
| --- | --- | --- | --- | --- | --- |
| pt-arche-kubernetes-cert-manager | `cert_manager_version` | OLD | NEW | #PR | vA.B.C |
| pt-arche-kubernetes-cert-manager | `cert_manager_istio_csr_version` | OLD | NEW | #PR | vA.B.C |
| pt-arche-kubernetes-datadog-operator | `operator_version` | OLD | NEW | #PR | vA.B.C |
| pt-arche-kubernetes-datadog-operator | `node_agent_tag`, `cluster_agent_tag` | OLD | NEW | #PR | vA.B.C |
| pt-arche-kubernetes-istio | `istio_version` | OLD | NEW | #PR | vA.B.C |
| pt-arche-kubernetes-opa-gatekeeper | `gatekeeper_version` | OLD | NEW | #PR | vA.B.C |

Mark rows with no change as "–". Include the PR URL for every PR that was opened.

> **Note:** These module releases update the upstream component versions inside each arche module. To propagate the new module SHAs to `pt-corpus` and `pt-pneuma`, run the `release-arche-modules` skill afterward.
