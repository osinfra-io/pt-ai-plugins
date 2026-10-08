---
name: release-arche-modules
description: Discover and release all pt-arche-* modules in dependency order, update canonical SHA pins, and optionally propagate releases to every Corpus and Pneuma deployment workspace. Use when asked to release or update arche modules.
---

# Release arche modules

Release the Arche module chain end-to-end. Ask before updating Tier 3 consumers unless the user already authorized them. Do not start releases when the user only asks to inspect or repair this skill.

Use the **create-pull-request** skill's sentence-case titles, commit trailer, and existing label taxonomy. Release PRs are ready for review rather than draft and may be merged autonomously. Apply existing `dependencies` and `opentofu` labels to pin updates, not `chore`. Never create labels to make a command succeed.

## 1. Preflight and discover

Resolve absolute checkout paths once. Every shell call starts in the session working directory: use `git -C "$REPO_DIR"` or begin with `cd "$REPO_DIR" &&`. Never run pre-commit from the aggregate Arche directory, which is not a Git repository.

Read applicable team and repository instructions. Check working trees and existing branches/PRs before editing; preserve unrelated work and reuse this release's existing PR instead of creating duplicates.

Discover active `osinfra-io/pt-arche-*` repositories, not just the table below. Compare remote discovery with local checkouts; clone missing module checkouts into the session workspace if needed. Never inspect `.terraform/` directories.

```bash
gh api --paginate 'orgs/osinfra-io/repos?per_page=100' \
  --jq '.[] | select(.archived == false and (.name | startswith("pt-arche-"))) | .name'
```

Classify `pt-arche-core-helpers` as Tier 1, reusable modules with release workflows as Tier 2, `pt-arche-child-module-template` as the untagged scaffold, and `pt-arche-ai-context` as instructions only. Inspect unfamiliar repositories before classifying them. Discover actual Arche module dependencies from tracked `.tofu` sources; if a module depends on another Tier 2 module, release and update that dependency first. Only independent modules are parallel-safe.

This table is a starting point, not a closed inventory. Inspect tracked helper files and resolve symlinks to verify canonical paths before editing.

| Tier | Repo | Canonical core-helper pin |
| --- | --- | --- |
| 1 | `pt-arche-core-helpers` | Foundation |
| 2 | `pt-arche-datadog-google-integration` | `helpers.tofu` |
| 2 | `pt-arche-google-cloud-sql` | `regional/helpers.tofu` |
| 2 | `pt-arche-google-kubernetes-engine` | `shared/helpers.tofu` |
| 2 | `pt-arche-google-network` | `shared/helpers.tofu` |
| 2 | `pt-arche-google-project` | `helpers.tofu` |
| 2 | `pt-arche-google-storage-bucket` | None |
| 2 | `pt-arche-kubernetes-agentgateway` | `shared/helpers.tofu` |
| 2 | `pt-arche-kubernetes-authentik` | None |
| 2 | `pt-arche-kubernetes-cert-manager` | `shared/helpers.tofu` |
| 2 | `pt-arche-kubernetes-datadog-operator` | `shared/helpers.tofu` |
| 2 | `pt-arche-kubernetes-istio` | `shared/helpers.tofu` |
| 2 | `pt-arche-kubernetes-opa-gatekeeper` | `shared/helpers.tofu` |
| scaffold | `pt-arche-child-module-template` | `skeleton/helpers.tofu`; never tag |
| 3 | `pt-corpus`, `pt-pneuma` | All deployment workspaces; confirmation required |

Before committing, check the existing signing configuration and main-branch signature requirements. Prefer signed commits from the outset when required. If signing fails, ask the user to configure/unlock their signing key and stop that repo. Do not investigate private keys, change global Git settings, amend commits, force-push, or create replacement branches/PRs as a signing workaround.

## 2. Detect and select versions

For each releasable repo, fetch `main` and tags and retrieve its latest published release once:

```bash
git -C "$REPO_DIR" fetch --quiet origin main --tags
gh release view --repo "osinfra-io/$REPO" --json tagName,url
```

Compare the released tag's commit with `origin/main`, not PR merge timestamps against `publishedAt`. Publication can lag behind the tag, and a default 30-PR list is incomplete. Use the commit range to detect all unreleased work, including direct commits:

```bash
git -C "$REPO_DIR" rev-list --count "$LATEST_TAG..origin/main"
git -C "$REPO_DIR" log --oneline "$LATEST_TAG..origin/main"
git -C "$REPO_DIR" diff --stat "$LATEST_TAG..origin/main"
```

Verify the release commit is an ancestor of `origin/main`. If no published release exists, inspect remote tags and release runs: an existing tag may be awaiting publication or have a failed workflow. Do not treat authentication/API errors as "no releases" or create a second tag for an unpublished release. For a genuinely untagged module with merged initial code, use the platform's initial `v0.1.0` release.

Select the highest applicable SemVer bump from the actual unreleased implementation and public interface:

- PATCH: fixes, refactoring that preserves behavior/state through migration blocks, dependency bumps, tests, or documentation.
- MINOR: backwards-compatible resources, inputs, outputs, or entry points.
- MAJOR: breaking input/output changes, incompatible defaults, or required consumer migration.

Read only relevant source diffs when commit summaries are insufficient. Do not decide a breaking change solely from a PR title or a declaration removed from one file; it may have moved to a shared file or been an unused input.

Maintain a compact per-repo record: previous tag, selected version, main SHA, canonical pins, release reason, PR URL, and status. Keep API output focused; avoid dumping every historical PR or repeatedly rediscovering the same facts.

## 3. Release the foundation

If Core Helpers has unreleased commits, tag its fetched `origin/main` as the selected version. Otherwise use the existing released SHA/version. Do not propagate an unreleased main tip under an older version comment.

Before every tag, verify the PR (if any) is merged, the target is on `main`, and the chosen tag is absent locally and remotely. Never move or overwrite an existing tag.

```bash
CORE_SHA=$(git -C "$REPO_DIR" rev-parse origin/main)
git -C "$REPO_DIR" tag "$NEXT_TAG" "$CORE_SHA"
git -C "$REPO_DIR" push origin "$NEXT_TAG"
```

Verify the tag-triggered release publishes before treating Core Helpers as released. Record the released SHA and version for dependent modules.

## 4. Update and release modules

Process modules in discovered dependency order. A module needs a release if it has unreleased commits or a released dependency pin needs updating. Modules without Core Helpers dependencies still need detection and releases; do not invent helper files for them.

If all dependency pins already match, tag the fetched main tip directly; do not create an empty branch or PR. Otherwise:

1. Branch from fetched `origin/main` using `update-core-helpers-to-<version>` for core-only updates, or a descriptive dependency-update name.
2. Edit each canonical source file once, updating full 40-character `ref=` SHAs and inline version comments. Preserve symlinks.
3. Run `pre-commit autoupdate --freeze` once per affected repo in this session, then `pre-commit run -a` before committing. If hooks modify files, inspect those changes and rerun only as needed. Do not update hooks again on retries.
4. Stage only task files. Use a signed commit when required, a sentence-case message such as `Update pt-arche-core-helpers to <version>`, and the Copilot co-author trailer.
5. Push, open one PR with a concise description, and apply existing `dependencies` and `opentofu` labels.
6. Merge using the policy below. Only after a verified merge, fetch `main`, record the post-merge SHA, tag the selected module version, and verify release publication.

**Validation failures:** do not silently skip hooks or expand into unrelated fixes. Report the failing hook and establish whether it also fails on unchanged main. Obtain explicit approval before bypassing a baseline failure; otherwise mark that repo blocked and continue independent work.

### Merge policy and bounded waits

If the user explicitly authorizes admin merging, use `gh pr merge "$PR_URL" --admin --squash --delete-branch` for this run's PRs after required local validation. Do not change branch rules or manufacture approvals.

Otherwise enable `--auto --squash --delete-branch`. Check merge state once after checks finish. If a review/policy gate still blocks it, ask once whether to admin-merge this run's PRs or leave them pending. Do not poll indefinitely, recreate PRs, request bot reviewers repeatedly, or tag unmerged changes. An admin merge does not waive local validation failures without explicit approval.

Allow a bounded wait of up to five minutes for checks or tag-triggered publication, using sensible intervals rather than rapid polling. If still blocked or unpublished, report the exact gate or release run and stop dependent operations; do not claim completion. User-approved background continuation must retain the recorded repo/PR state.

After Tier 2, update the scaffold's canonical pin using the same commit/merge flow only if it differs. Do not tag the scaffold.

## 5. Update confirmed consumers

Ask whether to update `pt-corpus`, `pt-pneuma`, both, or neither, unless already authorized. Use `update-arche-modules-YYYYMMDD` branches and the same validation, signing, labels, and merge policy.

Discover **every tracked deployment `.tofu` source recursively**, including root, `regional/`, onboarding, nested add-ons, and canonical `shared/helpers.tofu` files. Do not limit updates to root `main.tofu` and `helpers.tofu`. Exclude downloaded caches and local test-only fixtures; inspect unfamiliar paths before excluding them.

For each confirmed consumer:

- Update every reference to each newly released module, preserving its `//submodule` path and updating the inline version comment.
- Update all canonical Core Helpers pins; resolve symlinks and edit their targets only once.
- Inspect consumer arguments for real breaking changes and make only the directly required migration.
- Do not introduce modules the consumer does not already use or replace unreleased branch pins without understanding why they exist.
- Before committing, compare all deployment pins against the release record. After merging, verify those pins on fetched `main` too. A root-only update is incomplete.

Use `Update arche modules to latest releases` for the commit/PR title and list changed module versions in the PR body. If all pins already match, report unchanged without opening a PR.

## 6. Verify and report

Confirm published releases and tag SHAs, merged PRs, canonical helper pins, and all confirmed consumer deployment pins. Return modified checkouts to up-to-date `main` and delete only this run's merged branches. Preserve unrelated branches and changes.

Build the summary from discovery, not a fixed list:

| Repo | Previous | New | PR / Status |
| --- | --- | --- | --- |
| `<discovered repo>` | `<previous tag or none>` | `<published version, pin, or unchanged>` | `<PR URL or exact blocker>` |

Include first releases, no-helper modules, the untagged scaffold, and confirmed consumers. Clearly distinguish published, pending, blocked, unchanged, and not requested. Never describe pending tags or partial consumer updates as complete.
