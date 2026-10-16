---
name: release-plugins
description: Check all osinfra-io Copilot CLI plugins for unreleased changes, cut any needed releases across the full dependency chain, and land the updates in pt-ai-plugins — without waiting for the user to do any manual steps. Use when asked to release, update, or sync plugins.
---

# Release plugins

Execute the full release chain autonomously. Do not pause to ask the user for confirmation between steps — work through the entire procedure and report a summary at the end.

> **PR conventions:** branch naming, sentence-case titles, no Conventional Commits prefix, and the `Co-authored-by` trailer follow the **create-pull-request** skill. The `copilot` label is available in every osinfra-io repository; apply it to plugin and skill release PRs. The commands below merge autonomously (`--auto`), unlike the approval-gated flow in create-pull-request. If branch rules block auto-merge because approval is required, leave auto-merge enabled and report the blocking requirement; do not bypass repository protections.

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

After each tag push in Steps 2–4, verify its release before continuing:

1. Set `GH_REPO` to the repository being released (for example, `osinfra-io/pt-techne-mcp-server`), resolve the exact tag commit, and find the `push` workflow run for that tag and commit:

   ```bash
   TAG=vX.Y.Z
   TAG_SHA=$(git rev-parse "$TAG")
   gh run list --repo "$GH_REPO" \
     --event push --branch "$TAG" --commit "$TAG_SHA" \
     --limit 20 \
     --json databaseId,headSha,headBranch,event,url
   ```

   If the run has not appeared yet, repeat the query every 15 seconds for up to five minutes. Select the run whose `headBranch` is the tag and whose `headSha` is `TAG_SHA`; do not use a run for another ref or commit.
2. Check that run with `gh run view <run-id> --repo "$GH_REPO" --json status,conclusion,url`. Wait for it to complete, checking every 15 seconds for up to five minutes. Continue only when `status` is `completed` and `conclusion` is `success`.
3. Confirm the matching published release with `gh release view "$TAG" --repo "$GH_REPO" --json tagName,url,publishedAt`. If it is not published yet, retry every 15 seconds for up to five minutes after the workflow succeeds.

If a run fails, no matching run appears, the release is not published by the deadline, or a GitHub query returns an error, stop this release chain. Report the tag, the run URL and status when available, and the missing or failed release; do not report that repo as released or continue to dependent releases. Keep the previous/new version summary and include any PR URLs already opened.

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
gh pr edit --add-label copilot
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
```

Choose an available dated update branch after checking both local and remote refs. If the base name is occupied, try deterministic numeric suffixes (`-2`, `-3`, and so on); do not reuse an existing branch:

```bash
BASE_BRANCH="update-plugins-$(date +%Y%m%d)"
BRANCH="$BASE_BRANCH"
SUFFIX=2
while :; do
  if git show-ref --verify --quiet "refs/heads/$BRANCH"; then
    BRANCH="${BASE_BRANCH}-${SUFFIX}"
    SUFFIX=$((SUFFIX + 1))
    continue
  fi
  REMOTE_REF=$(git ls-remote --heads origin "refs/heads/$BRANCH") || {
    echo "Unable to check remote branch refs" >&2
    exit 1
  }
  if [ -z "$REMOTE_REF" ]; then
    break
  fi
  BRANCH="${BASE_BRANCH}-${SUFFIX}"
  SUFFIX=$((SUFFIX + 1))
done
git checkout -b "$BRANCH" origin/main
```

Edit `.github/plugin/marketplace.json` with the new refs and versions. If `plugins/platform-grouping/plugin.json` was also bumped, stage it alongside the marketplace file and mention its new version in the PR body — omit the `platform-grouping` bullet and the `plugin.json` path below when that file didn't change.

```bash
git add .github/plugin/marketplace.json plugins/platform-grouping/plugin.json
git commit -m "Update plugins to latest releases"   -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
git push -u origin "$BRANCH"
gh pr create   --title "Update plugins to latest releases"   --body "Bumps federated plugins to their latest releases.

- techne-agents: vA.B.C (pt-techne-mcp-server vX.Y.Z)
- platform-grouping: vD.E.F (skill content changed)"
gh pr edit --add-label copilot
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

| Repo | Previous | New | PR / Status |
| --- | --- | --- | --- |
| pt-techne-mcp-server | vOLD | vNEW | PR URL or verified / incomplete status |
| pt-techne-agents | vOLD | vNEW | PR URL or verified / incomplete status |
| pt-ai-plugins | vOLD | vNEW | PR URL or verified / incomplete status |

Include the PR URL for any PR that was opened. Mark a repo as incomplete rather than released if its tag-triggered workflow or GitHub Release was not verified; include the run URL and failure or timeout details.
