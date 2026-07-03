# Platform AI Plugins

[![Dependabot](https://img.shields.io/github/actions/workflow/status/osinfra-io/pt-ai-plugins/dependabot.yml?style=for-the-badge&logo=github&color=2088FF&label=Dependabot)](https://github.com/osinfra-io/pt-ai-plugins/actions/workflows/dependabot.yml)

The osinfra-io platform [GitHub Copilot CLI plugin](https://docs.github.com/en/copilot/concepts/agents/copilot-cli/about-cli-plugins) marketplace. This is the group-level, installable counterpart to [`pt-ai-context`](https://github.com/osinfra-io/pt-ai-context): where `pt-ai-context` holds always-on custom instructions, this repo distributes on-demand **skills, agents, and MCP integrations** as versioned plugins.

## Installation

Register the marketplace once, then install the plugins you want:

```bash
copilot plugin marketplace add osinfra-io/pt-ai-plugins
copilot plugin install platform-conventions@osinfra-io
copilot plugin install nomos-agent@osinfra-io
```

Browse everything available in the marketplace:

```bash
copilot plugin marketplace browse osinfra-io
```

## Plugins

| Plugin | Description | Source |
| --- | --- | --- |
| [platform-conventions](plugins/platform-conventions) | Shared platform workflows as Copilot skills (e.g. `create-pull-request`, `address-review-comments`) | this repo |
| [nomos-agent](https://github.com/osinfra-io/pt-techne-agents) | The Nomos onboarding agent and its `pt-techne-mcp-server` tools | federated from `pt-techne-agents` |

### nomos-agent requirements

The `nomos-agent` plugin runs the `pt-techne-mcp-server` as a Docker container. It requires:

- **Docker** — the MCP server runs via `docker run`
- **`NOMOS_GITHUB_TOKEN`** — must be set in your environment; the MCP server uses it to read team specs, compute CIDRs, look up users, and open pull requests on your behalf

```bash
export NOMOS_GITHUB_TOKEN=<your-token>
```

Without `NOMOS_GITHUB_TOKEN`, read tools return `not_configured` and write tools (PR creation) will not work.

## Plugins vs instructions

Plugins **complement** custom instructions — they do not replace them. The Copilot CLI `plugin.json` manifest has no field for custom instructions, so `copilot-instructions.md` and `*.instructions.md` remain distributed through [`pt-ai-context`](https://github.com/osinfra-io/pt-ai-context) and `COPILOT_CUSTOM_INSTRUCTIONS_DIRS`. Use this marketplace for cross-cutting **capabilities** (skills, agents, MCP servers) that should be installable from any directory.

## Contributing

Each plugin is a directory under `plugins/` containing a `plugin.json` manifest. The marketplace is defined in [`.github/plugin/marketplace.json`](.github/plugin/marketplace.json).

Team-owned plugins may be **federated** — their `plugin.json` lives in the team's own repository and `marketplace.json` references it via `source: osinfra-io/<repo>`, avoiding duplication.

Releases follow the platform convention — push a `vX.Y.Z` tag and the [release workflow](.github/workflows/release.yml) publishes automatically.
