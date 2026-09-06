---
name: release-plugins
description: Check all osinfra-io Copilot CLI plugins for unreleased changes, cut any needed releases across the full dependency chain, and land the updates in pt-ai-plugins — without waiting for the user to do any manual steps. Use when asked to release, update, or sync plugins.
---

# Release plugins

Execute the full release chain autonomously. Do not pause to ask the user for confirmation between steps — work through the entire procedure and report a summary at the end.

> **PR conventions:** branch naming, sentence-case titles, no Conventional Commits prefix, the `Co-authored-by` trailer, and the label taxonomy all follow the **create-pull-request** skill — that skill is the single source of truth for those mechanics. The commands below apply the release-specific titles and labels and merge autonomously (`--auto`), unlike the approval-gated flow in create-pull-request.

## Dependency chain

Federated plugins in `pt-ai-plugins` have upstream source repos. Changes must propagate in dependency order before `pt-ai-plugins` can be updated.

Current chain:

```text
pt-techne-mcp-server  →  pt-techne-agents  →  pt-ai-plugins
```

## Step 1 — Detect what needs releasing

For each repo in the chain, get the latest release and compare its publish date against recently merged PRs:

```bash
gh release view --repo osinfra-io/pt-techne-mcp-server --json tagName,publishedAt
gh pr list --repo osinfra-io/pt-techne-mcp-server --state merged   --json number,title,mergedAt

gh release view --repo osinfra-io/pt-techne-agents --json tagName,publishedAt
gh pr list --repo osinfra-io/pt-techne-agents --state merged   --json number,title,mergedAt
```

A repo needs a new release if any PR merged **after** the latest release's `publishedAt`.

Determine the next version for each repo using [Semantic Versioning](https://semver.org/):

- PATCH — bug fixes, dependency bumps, prompt tweaks
- MINOR — new tools, new schema fields, new agent capabilities
- MAJOR — breaking changes to the API or schema

## Step 2 — Release pt-techne-mcp-server (if needed)

Get the current tip of `main` and tag it:

```bash
cd pt-techne-mcp-server
git fetch origin main
git log origin/main --oneline -1
git tag vX.Y.Z <sha>
git push origin vX.Y.Z
```

## Step 3 — Release pt-techne-agents (if needed)

If a new `pt-techne-mcp-server` was released in Step 2, update the pinned image tag in `.mcp.json` before releasing the agents repo. If no MCP server bump is needed, skip that edit and release only the plugin version.

In all cases, `pt-techne-agents` uses the same release flow: optionally edit `.mcp.json`, always bump the `version` field in `plugin.json` to the next semver, then commit, merge, and tag.

```bash
cd pt-techne-agents
git checkout main && git pull
git checkout -b release-vA.B.C
```

If the MCP server version changed, edit `.mcp.json` and replace the image tag:

```json
"ghcr.io/osinfra-io/pt-techne-mcp-server:vX.Y.Z"
```

Always edit `plugin.json` and set `"version": "A.B.C"`.

Commit the changed file set (`plugin.json` plus `.mcp.json` when applicable), push, open the PR, label it, and squash-merge:

```bash
git add plugin.json .mcp.json
git commit -m "Release vA.B.C"   -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
git push -u origin release-vA.B.C
gh pr create   --title "Release vA.B.C"   --body "Bumps plugin.json for the next release and updates the pt-techne-mcp-server image tag to vX.Y.Z when required."
gh pr edit --add-label chore
gh pr merge --squash --delete-branch --auto
```

Wait for the merge to complete, then fetch and tag:

```bash
git checkout main && git pull
git log --oneline -1
git tag vA.B.C
git push origin vA.B.C
```

## Step 4 — Update pt-ai-plugins

Read `.github/plugin/marketplace.json` directly to identify which plugins need their `ref` or `version` bumped.

For each federated plugin with a new upstream release, update its `ref` and `version`. Also increment the top-level marketplace `version` (patch bump). Additionally, bump `plugins/platform-grouping/plugin.json` version if any platform-grouping skill content changed since the last release.

```bash
cd pt-ai-plugins
git checkout main && git pull
git checkout -b update-plugins-YYYYMMDD
```

Edit `.github/plugin/marketplace.json` with the new refs and versions.

```bash
git add .github/plugin/marketplace.json
git commit -m "Update plugins to latest releases"   -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
git push -u origin update-plugins-YYYYMMDD
gh pr create   --title "Update plugins to latest releases"   --body "Bumps federated plugins to their latest releases.

- techne-agents: vA.B.C (pt-techne-mcp-server vX.Y.Z)"
gh pr edit --add-label chore
gh pr merge --squash --delete-branch --auto
```

After merge, tag a new `pt-ai-plugins` release:

```bash
git checkout main && git pull
git log --oneline -1
git tag vN.N.N
git push origin vN.N.N
```

## Step 5 — Report

Summarise what was done:

| Repo | Previous | New |
| --- | --- | --- |
| pt-techne-mcp-server | vOLD | vNEW |
| pt-techne-agents | vOLD | vNEW |
| pt-ai-plugins | vOLD | vNEW |

Include the PR URL for any PR that was opened.
