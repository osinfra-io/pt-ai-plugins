---
name: local-integration-testing
description: Exercise checked-out Authentik, Istio ambient, agentgateway, Agent Substrate, kagent, and OpenBao configuration together in dedicated Docker Desktop Kind Kubernetes before optional sandbox deployment. Runs the pt-pneuma tests/integration suite and coordinates real Google browser sign-in.
---

# Test local integration

This is an **opt-in developer integration test for complex configuration changes**, not a mandatory pre-push check or CI gate. The whole stack, including Authentik and local PostgreSQL, runs in Kubernetes. Keep mocked OpenTofu tests separate.

All fixtures, shared helpers, hostnames, and verifiers live in `pt-pneuma/tests/integration/` (see its `README.md`). Run only its checked-in entry points. Do not write one-off shell commands, inline programs, ad-hoc Helm commands, or test YAML to manipulate the cluster or perform required checks. If a required behavior is not covered, add a reusable, tested helper to `pt-pneuma/tests/integration` before running it. Diagnose failures explicitly and stop before destructive migration or interactive sign-in when they cannot be completed safely. Never report full integration success without observed Google sign-in and identity verification.

## Prerequisites

Use the aggregated workspace layout: module repositories under `arche/`, `pt-pneuma` and `pt-pneuma-istio-test` under `pneuma/`, and `logos/pt-logos`. Fixtures use the checked-out modules (including uncommitted edits) through relative sources; do not claim arbitrary sibling-clone layouts work. Exclude `.terraform/` entirely. Read each repository's instructions before changing it.

Run everything from `pt-pneuma`. The preflight (`tests/integration/shared/preflight.sh`, run by `setup.sh`) checks Docker, the explicit `docker-desktop` context, Docker Desktop's **Kind** provisioner, ambient mount propagation, and fixture ownership. On an unowned cluster it automatically records ownership only when no non-system namespaces, Helm installations, or gateway/mesh CRDs exist. A context name or matching resource name does not establish ownership.

Do not silently change contexts, adopt existing resources, uninstall existing installations, purge CRDs, or reset Docker Desktop Kubernetes. Allocate enough CPU/memory for the ambient and application workloads and never fall back to sidecars.

Agent Substrate needs the `certificates.k8s.io/v1beta1` API and the `ClusterTrustBundle`, `ClusterTrustBundleProjection` and `PodCertificateRequest` feature gates on the Kind node (kube-apiserver and kubelet), plus `go` to run upstream `ate-setup`. If the API is missing, run `tests/integration/agent-substrate/enable-feature-gates.sh --enable`; it checks for a supported single-node Kubernetes version, enables the gates, and waits for readiness. The helper uses and removes temporary working files; it does not retain node-config backups or restore edits automatically. This is a dedicated local cluster, so do not pause for separate authorization. If an edit fails after changing the node, reset Docker Desktop Kubernetes before retrying. Docker Desktop updates and resets may undo the gates.

Real Google authentication requires `TF_VAR_google_oauth_client_id` and `TF_VAR_google_oauth_client_secret`. Never print their values, persist them in tracked files, or log tokens, cookies, callback codes, or identity JSON. The Google web client must allow:

```text
https://localhost/source/oauth/callback/google/
```

The gateway rewrites Google source requests to the `localhost` Host and returns the callback to `authentik.localhost`, where the session is held. Keep this contract; Google does not accept `.localhost` subdomains as redirect URIs.

## Setup and iteration

Run `tests/integration/setup.sh`. On an unowned cluster, preflight refuses setup if it finds a non-system namespace, Helm release, or gateway/mesh CRD. If the cluster passes those emptiness checks, preflight records ownership and removes the known component `.work` directories (`istio`, `authentik`, `agentgateway`, `agent-substrate`, `kagent`, and `openbao`) before setup. This intentionally clears state and generated local credentials left behind after a cluster reset; provide the Google OAuth variables again. On an already-owned cluster, preflight leaves `.work` untouched. If an ownership marker belongs to another owner or any emptiness check fails, stop and resolve the cluster instead of adopting resources or deleting state.

```bash
tests/integration/setup.sh
```

If a checked-in script is itself broken, fix it with the edit tool as a small reusable change in `pt-pneuma/tests/integration` (with a test where one exists) and open a PR for it. Do not work around it with inline commands or rewrite files with scripts. Prefer one definition of shared constants, such as `shared/owner.sh`, over redeclaring them in component scripts.

The order is Istio ambient runtime and shared gateway, Authentik (local PostgreSQL, real deployment and configuration modules), browser-auth policies and routes, agentgateway, Agent Substrate, kagent, then OpenBao. Do not apply every root at once; Kubernetes manifest providers need CRDs at plan time. Components can be rerun individually (`tests/integration/<component>/setup.sh`, plus `istio/apply-auth.sh` and `istio/apply-routes.sh`) after editing the matching checked-out module without resetting the database.

Give the developer concise progress updates throughout setup and verification: announce the current stage, report each component as its checked-in script confirms completion, and identify any failed stage and what remains. Include the relevant browser URL from Browser verification when its route is configured; label it as awaiting verification until the checks and sign-in have actually succeeded. Treat component setup, automated verification, configuration parity, and Google browser sign-in as separate milestones. Do not infer readiness from startup alone or expose secrets, identity data, or sensitive callback URLs in updates.

If Authentik reports a unique-name conflict for its built-in brand, embedded outpost, or default identification stage, stop rather than rerunning setup or resetting the database. Preserve the `.work` state and the running cluster; reconcile the state with the current Authentik instance explicitly before retrying.

For a fresh database the test-only administrator is `akadmin` / `akadmin` at `https://authentik.localhost/if/admin/`; never use that password elsewhere. Credentials, OpenBao's root token and unseal key, and state live in ignored `.work/` directories. Never print the Google OAuth values, the `akadmin` password, or the unseal key. The exception is OpenBao's root token, a throwaway for the local cluster: after setup, run `tests/integration/openbao/show-credentials.sh` and give the developer the OpenBao URL (`https://openbao.localhost/ui/`) and printed root token as a local administrative fallback. Prefer the configured OIDC method when testing the new login integration; the root token is not an OIDC login.

### Developer handoff

After setup, explain how to test a change:

- Edit checked-out code, then rerun the owning component setup (or `apply-auth.sh` / `apply-routes.sh` for shared browser policies and routes).
- Run `tests/integration/verify.sh`, then exercise the changed behavior through the browser URLs below. Check expected access and denial; healthy services alone do not verify the change.
- Do not tear down during normal iteration. Teardown deletes local users, memberships, and database data.
- Explain the fidelity boundary: authentication configuration and Istio browser-auth rendering are shared with the cloud; local domains, OAuth client/callback, application IDs, and explicit local groups substitute for cloud discovery. PostgreSQL, upstream images, local TLS, and Kind substitute for Cloud SQL, mirrored registries, cloud certificates, Workload Identity, and GCP networking. Cloud root discovery, environment enablement, and multi-region behavior still require sandbox verification.
- Local testing does not deploy sandbox or update released module pins.
- Include the OpenBao UI method/role, certificate-aware CLI command, and hostname-resolution prerequisites from Browser verification in the handoff.

To add a component host, edit `tests/integration/shared/hostnames.txt` and the routes in `pt-pneuma`; no module repository changes.

## Automated verification

```bash
tests/integration/verify.sh
```

It runs each component verifier, the holistic HTTP verifier, then the runtime verifier. It stops on the first failed stage, leaves the fixtures running, and never tears down as a fallback. Do not replace it with hand-built `kubectl`, `curl`, or metric commands.

For configuration-parity iterations, apply the edited configuration using its owning script, then use the HTTP verifier's bounded expected-status mode to wait for gateway policy propagation:

```bash
python3 tests/integration/verify/verify-http.py --expect-status 302 --timeout 120 \
  https://dev.localhost/istio-test/metadata/cluster-name
```

Use the expected status for the specific temporary behavior, restore the intended configuration, reapply it, and wait for the original status the same way. A single immediate sample can race Istio propagation.

A passing run covers ready Authentik/Istio/agentgateway/Agent Substrate/kagent/OpenBao and diagnostic workloads; Authentik branding, flow, stage and policy parity plus a test-administrator login (not Google verification); Programmed gateways and Accepted/ResolvedRefs routes; ambient enrollment without sidecars; exact `200` for public endpoints and exact `302` to Authentik for protected paths with and without forged identity headers; Authentik protection of the agentgateway admin UI and the kagent UI (`kagent.localhost`, kagent Admins group); OpenBao health and denied unauthenticated or forged-token access; fail-closed behavior with Authentik scaled to zero (protected requests denied with HTTP 403, or a connection failure reported as status `000` with a nonzero curl exit) and restored (HTTP 302 recovery required); in-mesh admin-port denial; and `mutual_tls` ztunnel metrics on every relevant node.

If restoration or recovery fails, state that explicitly, do not continue, and diagnose with the owning Authentik component script. Do not manually scale workloads with ad-hoc commands. Do not report the fail-closed check as successful until restoration and recovery were both observed.

## Browser verification

Leave the fixtures running and direct the developer to:

```text
https://dev.localhost/istio-test/auth
https://agentgateway.localhost/agentgateway-test/auth
https://agentgateway.localhost/ui/
https://kagent.localhost/
https://openbao.localhost/ui/
```

For the OpenBao OIDC check, choose **OIDC** in the UI and use role `default`, then complete Google sign-in through Authentik. From the `pt-pneuma` repository root, in a browser-enabled terminal with `bao` installed, use:

```bash
BAO_CACERT="$PWD/tests/integration/istio/.work/gateway-localhost.crt" \
BAO_ADDR=https://openbao.localhost \
bao login -method=oidc -path=oidc role=default
```

The CLI must trust the fixture gateway certificate using `BAO_CACERT`; accepting a browser certificate warning does not establish CLI trust. Keep TLS verification enabled.

Both `openbao.localhost` and `authentik.localhost` must resolve to the gateway from the CLI and browser environments. Browsers may resolve `*.localhost` internally while the CLI's system resolver returns “no such host.” When the gateway is reachable on the CLI machine's loopback, the developer can add this `/etc/hosts` entry:

```text
127.0.0.1 openbao.localhost authentik.localhost
```

For a container or remote shell, establish the reachable gateway address instead of assuming its loopback is the desktop's. The browser must also be able to reach the CLI callback listener at `http://localhost:8250/oidc/callback`.

OIDC login only receives team policies when the authenticated user's local Authentik `groups` claim contains a group mapped to an OpenBao identity-group alias. Check access with a user whose local membership is configured; a successful login alone does not prove team access. Use the printed local root token with the UI's **Token** method only as the administrative fallback, for example when OIDC is unavailable. Do not report Google sign-in or group-claim verification as complete unless it was observed.

Accept the temporary certificate warning and sign in through Google. Both diagnostic paths must return the actual user's trusted `x-authentik-*` identity as JSON (headers, not a bearer JWT). Verify forged identity headers cannot override the actual user. Remove the test user's required local group membership, require denial, then restore membership and verify recovery. Do not change Google/production groups or retain personal identity output in session artifacts. Never offer a direct port-forward as an authenticated UI path.

If browser automation or the developer is unavailable, including unattended or autopilot runs, stop with **automated checks passed; Google browser verification pending**, allowed only after `verify.sh` exited successfully. Leave the fixtures running and include the URLs, OpenBao credentials, and remaining manual steps in the final report. If any automated check or restoration failed, report that failure instead.

Configuration parity is required for a full report: change a relevant checked-out policy or configuration, apply it with its owning script, observe the expected change with `verify-http.py --expect-status`, then restore, reapply, and observe the original status. If you skip it, state that explicitly in the report.

## Diagnostics

| Failure | Inspect |
| --- | --- |
| Cluster preflight rejects setup | Existing namespaces, Helm installations, gateway/mesh CRDs, or a foreign ownership marker; preserve the existing stack and resolve its ownership |
| Authentik reports a unique-name conflict for a built-in object | Local `.work` state provenance and the current Authentik instance; preserve both and stop before retrying or resetting the database |
| Authentik bootstrap/API objects not ready | Kubernetes PostgreSQL/server/worker status and redacted logs |
| Ambient enrollment fails | Kind provisioner, mount propagation, CNI and ztunnel logs |
| Public endpoints redirect or protected requests bypass sign-in | Shared authorization inputs, gateway policies, inbound header stripping, ingress logs |
| Agentgateway route/proxy fails | Chart availability, staged CRDs, route-parent conditions, ReferenceGrant, proxy/controller logs |
| Substrate or kagent controller cannot start | `substrate-podcert` controller and CA pools in `podcertificate-controller-system`, the `ate.dev/api-access=true` label on the kagent namespace, Postgres Secrets and grants, `ate-api-authentication` ConfigMap |
| Browser callback fails | Registered Google localhost URI, Host rewrite, callback redirect, Authentik session host |
| OpenBao CLI reports unknown certificate authority | Use the fixture gateway certificate with `BAO_CACERT` as shown above |
| OpenBao callback reports no code or ID token | Inspect only OAuth `error` / `error_description`, not full callback URLs; run `python3 tests/integration/authentik/diagnose-access.py` for redacted server diagnostics. An `Invalid grant_type for provider` rejection requires `authorization_code` on the dedicated Authentik OpenBao provider; correct the module, rerun Authentik setup and both component verifiers, then start a fresh login |
| In-mesh traffic resets or returns 503 | Workload endpoints, ztunnel identities, mTLS metrics and certificate readiness |

Use bounded waits. Do not downgrade Istio or agentgateway to sidestep incompatibilities; report a blocked version with evidence. Local success does not validate GCP load balancing, Cloud Armor, Workload Identity, Cloud SQL, multi-region behavior, or the full sandbox deployment.

## Cleanup

Cleanup is explicit and owned-resource-only; it deletes all fixture namespaces, including local users and PostgreSQL data:

```bash
tests/integration/teardown.sh
```

It stops OpenBao, kagent, Agent Substrate, agentgateway, Authentik, and Istio, after checking ownership. Generated credentials remain in `.work/`. Agentgateway's CRDs are deliberately retained by a local post-renderer. Do not remove cluster-wide CRDs or unowned installations, and report retained namespaces, data, and helper processes accurately.

When tearing down fixtures individually, tear down kagent before Agent Substrate: the substrate uninstall hangs while kagent's WorkerPool still exists. The Agent Substrate teardown removes the `substrate-podcert` release and namespace only when setup labelled that namespace `local-fixture.osinfra.io/owner=agent-substrate`; an unlabelled one is skipped. Teardown does not undo the Docker Desktop node edits (kube-apiserver and kubelet feature gates); reset Docker Desktop Kubernetes to revert them.
