---
name: release-plugins
description: Check all osinfra-io Copilot CLI plugins for unreleased changes, cut any needed releases across the full dependency chain, and land the updates in pt-ai-plugins — without waiting for the user to do any manual steps. Use when asked to release, update, or sync plugins.
---

# Release plugins

Execute the full release chain autonomously. Do not pause to ask the user for confirmation between steps — work through the entire procedure and report a summary at the end.

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
gh pr list --repo osinfra-io/pt-techne-mcp-server --state merged \
  --json number,title,mergedAt

gh release view --repo osinfra-io/pt-techne-agents --json tagName,publishedAt
gh pr list --repo osinfra-io/pt-techne-agents --state merged \
  --json number,title,mergedAt
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

If a new `pt-techne-mcp-server` was released in step 2, the agents repo must pin the new image tag before releasing. If only agent prompt changes are unreleased, skip straight to tagging.

**When the MCP server version changed:**

```bash
cd pt-techne-agents
git checkout main && git pull
git checkout -b update-mcp-server-to-vX.Y.Z
```

Edit `.mcp.json` — replace the image tag:

```json
"ghcr.io/osinfra-io/pt-techne-mcp-server:vX.Y.Z"
```

Bump the `version` field in `plugin.json` to the next semver.

```bash
git add .mcp.json plugin.json
git commit -m "Update pt-techne-mcp-server to vX.Y.Z" \
  -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
git push -u origin update-mcp-server-to-vX.Y.Z
gh pr create \
  --title "Update pt-techne-mcp-server to vX.Y.Z" \
  --body "Bumps the MCP server Docker image to vX.Y.Z."
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

**When only agent changes are unreleased** (no MCP server bump needed):

```bash
cd pt-techne-agents
git fetch origin main
git log origin/main --oneline -1
git tag vA.B.C <sha>
git push origin vA.B.C
```

## Step 4 — Update pt-ai-plugins

Read the current marketplace to identify which plugins need their `ref` or `version` bumped:

```bash
cat .github/plugin/marketplace.json
```

For each federated plugin with a new upstream release, update its `ref` and `version`. Also increment the top-level marketplace `version` (patch bump).

```bash
cd pt-ai-plugins
git checkout main && git pull
git checkout -b update-plugins-YYYYMMDD
```

Edit `.github/plugin/marketplace.json` with the new refs and versions.

```bash
git add .github/plugin/marketplace.json
git commit -m "Update plugins to latest releases" \
  -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
git push -u origin update-plugins-YYYYMMDD
gh pr create \
  --title "Update plugins to latest releases" \
  --body "$(printf 'Bumps federated plugins to their latest releases:\n\n- nomos-agent: vA.B.C (pt-techne-mcp-server vX.Y.Z)')"
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
|---|---|---|
| pt-techne-mcp-server | vOLD | vNEW |
| pt-techne-agents | vOLD | vNEW |
| pt-ai-plugins | vOLD | vNEW |

Include the PR URL for any PR that was opened.
