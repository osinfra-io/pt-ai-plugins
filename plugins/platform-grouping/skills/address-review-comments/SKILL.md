---
name: address-review-comments
description: Address all unresolved PR review comment threads — fix what needs fixing, explain what doesn't, and land everything in a single commit. Use when asked to address, fix, or resolve review comments on a pull request.
---

# Address review comments

Follow this procedure to address every unresolved review thread on the current pull request.
All code changes are committed together in **one commit** before any thread is replied to or resolved.

## 1. Identify the current pull request

```bash
gh pr view --json number,headRefName,baseRefName
```

Note the PR number and the `owner`/`repo` for the MCP tool calls below.

## 2. Fetch all unresolved review threads

Use the GitHub MCP server to retrieve all review threads:

```
github-mcp-server-pull_request_read
  method: get_review_comments
  owner: <owner>
  repo: <repo>
  pullNumber: <number>
```

The tool returns `review_threads` with `is_resolved`, `path`, `line`, `id` (thread node ID), and nested `comments` (each with `body`, `author`, `html_url`). Filter to threads where `is_resolved` is `false`. Work only with those threads.

## 3. Analyze every unresolved thread

For each unresolved thread, read the comment body and the file context at `path`/`line`.
Decide one of two outcomes:

| Outcome | Criteria |
|---|---|
| **Fix** | The comment identifies a real issue — a bug, a convention violation, a missing validation, incorrect logic, etc. |
| **Dismiss** | The comment is already addressed, is a matter of style with no clear-cut answer, is out of scope, or is factually incorrect. |

Collect **all** decisions before touching any file. Do not commit or reply yet.

## 4. Apply all fixes

Make every code change identified in step 3. Work across all affected files in one pass.
Do not create any intermediate commits.

If no thread requires a code change, skip to step 6 (no commit needed).

## 5. Create a single commit

After all edits are complete, stage everything and commit once:

```bash
git add -A
git commit -m "<concise sentence-case summary of what the review comments addressed>" \
  -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
git push
```

- Write the message in **sentence case**, no Conventional Commits prefix.
- If multiple unrelated areas were changed, list them briefly in the message body.

## 6. Reply and resolve each thread

For each unresolved thread, submit a review comment explaining what was done, then resolve:

```
github-mcp-server-pull_request_review_write
  method: create
  owner: <owner>
  repo: <repo>
  pullNumber: <number>
  event: COMMENT
  body: "<summary of fixes applied and dismissals explained>"
```

Then resolve each thread:

```
github-mcp-server-pull_request_review_write
  method: resolve_thread
  owner: <owner>
  repo: <repo>
  pullNumber: <number>
  threadId: <thread node ID from step 2>
```

Reply text guidelines:

- **Fixed:** Describe what was changed and where (e.g. *"Fixed — removed the inline conditional from the module block and moved it to `locals.tofu` as `local.dns_name`."*)
- **Dismissed:** Explain concisely why no change was made (e.g. *"No change needed — this output is already consumed by the `corpus` workspace via `module.core_helpers`."*)

All threads must be resolved by the end of this procedure.
