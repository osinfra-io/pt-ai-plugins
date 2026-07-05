---
name: update-nomos-release
description: Keep the nomos-agent release chain in sync — check for unreleased changes in pt-techne-mcp-server and pt-techne-agents, cut releases as needed, and update pt-ai-plugins. Use when asked to update, release, or sync the nomos-agent or mcp-server.
---

# Update nomos-agent release chain

The nomos-agent plugin is a three-tier release chain. Always propagate changes in order:

```
pt-techne-mcp-server  →  pt-techne-agents  →  pt-ai-plugins
```

## 1. Check for unreleased changes

Find the latest release tag in each repo and check if any commits have merged since:

```bash
# Check pt-techne-mcp-server
gh release list --repo osinfra-io/pt-techne-mcp-server --limit 1
gh pr list --repo osinfra-io/pt-techne-mcp-server --state merged --json title,mergedAt,number \
  | python3 -m json.tool

# Check pt-techne-agents
gh release list --repo osinfra-io/pt-techne-agents --limit 1
gh pr list --repo osinfra-io/pt-techne-agents --state merged --json title,mergedAt,number \
  | python3 -m json.tool
```

Compare each repo's latest release `publishedAt` against the most recent merged PR `mergedAt`. If any PRs merged after the release date, that repo needs a new release.

## 2. Release pt-techne-mcp-server (if needed)

Tag the current tip of `main`. The release workflow generates notes automatically.

```bash
cd pt-techne-mcp-server
git fetch
# Increment patch for backwards-compatible changes; minor for new tools/schema fields; major for breaking changes
git tag vX.Y.Z <commit-sha>
git push origin vX.Y.Z
```

Wait for the release workflow to publish before proceeding.

## 3. Release pt-techne-agents (if needed)

The agents repo pins the MCP server image tag in `.mcp.json`. If a new MCP server version was released in step 2, or if changes to the agent prompt are unreleased, update and re-release.

```bash
cd pt-techne-agents
git checkout main && git pull
git checkout -b update-mcp-server-to-vX.Y.Z
```

Update the image tag in `.mcp.json`:

```json
"ghcr.io/osinfra-io/pt-techne-mcp-server:vX.Y.Z"
```

Bump the `version` field in `plugin.json` to match the next semver.

Commit, push, and open a PR:

```bash
git add .mcp.json plugin.json
git commit -m "Update pt-techne-mcp-server to vX.Y.Z" \
  -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
git push -u origin update-mcp-server-to-vX.Y.Z
gh pr create --title "Update pt-techne-mcp-server to vX.Y.Z" --body "Bumps the MCP server image to vX.Y.Z."
gh pr edit --add-label chore
```

After the PR is squash-merged, fetch `main` and tag the merge commit:

```bash
git checkout main && git pull
git tag vA.B.C
git push origin vA.B.C
```

## 4. Update pt-ai-plugins

After both upstream repos are released, update the marketplace to point to the new agent tag.

```bash
cd pt-ai-plugins
git checkout main && git pull
git checkout -b update-nomos-agent-to-vA.B.C
```

In `.github/plugin/marketplace.json`, update the `nomos-agent` entry:

```json
{
  "name": "nomos-agent",
  "version": "A.B.C",
  "source": {
    "source": "github",
    "repo": "osinfra-io/pt-techne-agents",
    "ref": "vA.B.C"
  }
}
```

Also increment the top-level marketplace `version`.

Commit, push, and open a PR:

```bash
git add .github/plugin/marketplace.json
git commit -m "Update nomos-agent to vA.B.C" \
  -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
git push -u origin update-nomos-agent-to-vA.B.C
gh pr create --title "Update nomos-agent to vA.B.C" --body "Bumps the nomos-agent plugin to vA.B.C (pt-techne-mcp-server vX.Y.Z)."
gh pr edit --add-label chore
```

After the PR is squash-merged, tag a new `pt-ai-plugins` release:

```bash
git checkout main && git pull
git tag vX.Y.Z
git push origin vX.Y.Z
```

## 5. Notify consumers

Consumers update their installed plugins with:

```bash
copilot plugin update nomos-agent@osinfra-io
copilot plugin update platform-conventions@osinfra-io

# or update everything at once
copilot plugin update --all
```
