---
name: local-integration-testing
description: Run the checked-in pt-pneuma integration stack for Authentik, Istio ambient, agentgateway, Agent Substrate, kagent, and OpenBao on Docker Desktop Kubernetes.
---

# Run local integration

This is an opt-in developer test for changes that cross component boundaries, not a pre-push check or CI gate. Run it from `pt-pneuma` in the aggregated workspace so fixtures use the checked-out modules. Do not read `.terraform/`.

Use the checked-in scripts under `tests/integration/`; do not replace them with one-off cluster commands. The local stack validates configuration and behavior, not GCP networking, Workload Identity, or multi-region deployment.

## Setup

Set `TF_VAR_google_oauth_client_id` and `TF_VAR_google_oauth_client_secret` if testing real Google sign-in. The Google web client must allow:

```text
https://localhost/source/oauth/callback/google/
```

The gateway rewrites the Google callback to `localhost` and returns the session to `authentik.localhost`. Never print or persist OAuth values, tokens, cookies, or callback codes.

Run:

```bash
tests/integration/setup.sh
```

Preflight uses the current `docker-desktop` Kind cluster. If it is unowned and empty (no non-system namespaces, active Helm releases, or gateway/mesh CRDs), it records ownership and clears the six fixture `.work` directories before setup. This removes stale local state and credentials after a cluster reset; provide OAuth variables again. An already-owned cluster keeps its `.work` data. If preflight finds existing resources or a foreign ownership marker, stop rather than adopting or removing them.

If Agent Substrate reports the certificate API is missing, `setup.sh` stops there. Run the following, then rerun `tests/integration/setup.sh`:

```bash
tests/integration/agent-substrate/enable-feature-gates.sh
```

This updates the dedicated single-node Docker Desktop cluster and waits for readiness. It uses temporary working files (host `.work` and node `/var/tmp`, removed on exit), not backups; if the update fails, reset Docker Desktop Kubernetes and retry.

Setup runs the components in the required order. To iterate, rerun only the affected component's `setup.sh` (or `istio/apply-auth.sh` / `istio/apply-routes.sh`). Do not tear down between ordinary edits; teardown deletes local users and database data.

## Automated verification

Run:

```bash
tests/integration/verify.sh
```

It checks component health, gateway routes and authorization, forged identity headers, fail-closed behavior and recovery, and ambient mTLS. It stops on failure and leaves the stack running. If recovery fails, report it and stop; do not continue as if verification passed.

For a policy-change check, use the HTTP verifier's bounded status mode after applying the change with its owning script, then restore and verify the original behavior:

```bash
python3 tests/integration/verify/verify-http.py --expect-status 302 --timeout 120 \
  https://dev.localhost/istio-test/metadata/cluster-name
```

## Google and browser checks

Automated verification does not complete Google browser sign-in. Leave fixtures running and direct the developer to:

```text
https://dev.localhost/istio-test/auth
https://agentgateway.localhost/agentgateway-test/auth
https://agentgateway.localhost/ui/
https://kagent.localhost/
https://authentik.localhost/
https://openbao.localhost/ui/
```

Accept the local certificate warning and sign in through Google. Verify the diagnostic paths identify the signed-in user, forged identity headers are ignored, and removing then restoring the user's local group membership denies then restores protected access. Do not retain personal identity output.

For OpenBao, choose **OIDC** in the UI with role `default`. From the repository root, the CLI can use the fixture certificate:

```bash
BAO_CACERT="$PWD/tests/integration/istio/.work/gateway-localhost.crt" \
BAO_ADDR=https://openbao.localhost \
bao login -method=oidc -path=oidc role=default
```

Ensure `openbao.localhost` and `authentik.localhost` resolve to the gateway and the browser can reach the CLI callback at `http://localhost:8250/oidc/callback`.

If browser sign-in cannot be completed, report **automated checks passed; Google browser verification pending** only when `verify.sh` passed. Include the URLs and remaining manual checks; do not claim full integration success.

## Cleanup

Run only when finished; this deletes fixture namespaces, local users, and database data:

```bash
tests/integration/teardown.sh
```

Teardown does not undo the Docker Desktop node feature-gate edits; reset Docker Desktop Kubernetes to revert them.
