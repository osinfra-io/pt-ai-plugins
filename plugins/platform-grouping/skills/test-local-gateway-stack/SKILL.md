---
name: test-local-gateway-stack
description: Exercise checked-out Authentik, Istio ambient, and agentgateway configuration together in dedicated Docker Desktop Kind Kubernetes before optional sandbox deployment. Coordinates repo-owned tests/kubernetes fixtures and real Google browser sign-in.
---

# Test the local gateway stack

This is an **opt-in developer integration test for complex configuration changes**, not a mandatory pre-push check or CI gate. Run the whole stack in Kubernetes, including Authentik and local PostgreSQL. Keep mocked OpenTofu tests separate.

Use the component scripts and this skill's checked-in verification scripts directly. Do not write one-off shell commands, inline programs, ad-hoc Helm commands, or test YAML to manipulate the cluster or perform required checks. If a required behavior is not covered by an existing script, add a reusable, tested helper to this skill or the owning component before running it. Diagnose failures explicitly and stop before destructive migration or interactive sign-in when those steps cannot be completed safely. Never report full integration success without observed Google sign-in and identity verification.

## Repository discovery

Locate these checkouts and read their repository/team instructions:

- `pt-arche-kubernetes-authentik`
- `pt-arche-kubernetes-istio`
- `pt-arche-kubernetes-agentgateway`
- `pt-pneuma-istio-test`
- `pt-pneuma` for the shared gateway-auth renderer and Authentik authentication module

Use the aggregated workspace layout: module repositories under `arche/`, application/consumer repositories under `pneuma/`. The local module sources use this relative checkout arrangement to share the actual Pneuma renderer without unpublished release pins. Do not claim arbitrary sibling-clone layouts work; arrange the required checkouts in the standard layout first. Exclude `.terraform/` entirely. Record absolute paths and run each command in its owning repository.

All three components participate in a holistic run. Do not silently omit agentgateway because a checkout is missing. Fixtures live in `tests/kubernetes/`; generated credentials, state, and provider files live in ignored `.work/` directories. Relative module sources exercise the developer's checked-out changes. Do not use Docker Compose or maintain a parallel Compose fixture.

## Prerequisites and ownership

Run `scripts/preflight.sh` relative to this skill directory. It checks Docker, the explicit `docker-desktop` context, Docker Desktop's **Kind** provisioner, ambient mount propagation, and fixture ownership.

On a fresh **dedicated** test cluster, run `scripts/preflight.sh --claim` to record ownership. It refuses existing namespaces, Helm installations, or gateway/mesh CRDs without an ownership record. Component scripts also require their own state. A context name or matching resource name does not establish ownership.

Do not silently change contexts, adopt existing resources, uninstall existing installations, purge CRDs, or reset Docker Desktop Kubernetes. If the cluster contains unowned resources, report that explicit adoption is required; do not fabricate local state or add an ownership marker to bypass the guard.

Allocate sufficient CPU/memory for the existing ambient and application workloads. Never fall back to sidecars to make the tests pass.

Real Google authentication requires both environment variables:

```text
TF_VAR_google_oauth_client_id
TF_VAR_google_oauth_client_secret
```

Never print their values, persist them in tracked files, or log tokens, cookies, callback codes, or identity JSON. The Google web client must allow:

```text
https://localhost/source/oauth/callback/google/
```

The gateway rewrites Google source requests to the `localhost` Host and returns the callback to `authentik.localhost`, where the session is held. Keep this contract; Google does not accept `.localhost` subdomains as redirect URIs.

## Setup and iteration

The dependency order is:

1. Gateway API CRDs and Istio ambient runtime.
2. Kubernetes PostgreSQL and Authentik runtime/configuration.
3. Shared ingress routing/auth policy and diagnostic workload.
4. Agentgateway deployment and its later CRD-dependent manifests.

From Istio, install the runtime and diagnostic workload first:

```bash
tests/kubernetes/setup.sh
```

Do not apply every root at once; Kubernetes manifest providers require CRDs at plan time.

From Authentik:

```bash
tests/kubernetes/setup.sh
```

This invokes the real deployment module with a local PostgreSQL Service, no Cloud SQL proxy, and no Workload Identity. It waits for built-in Authentik objects, imports the embedded outpost and identification stage, and invokes the actual `regional/config` module. Administrative access is a transient loopback-only forward on port `19443`; browser traffic uses `https://authentik.localhost`. It stops the forward when the command exits.

For a fresh local database, the test-only administrator login is `akadmin` / `akadmin` at `https://authentik.localhost/if/admin/`. Never use this password outside the dedicated local fixture. Database credentials, API tokens, and signing keys remain generated. Bootstrap does not overwrite passwords in a retained database.

The login at `authentik.localhost` uses Pneuma's checked-out `regional/authentik-config/authentication` child module: the sandbox CSS, dark theme, osinfra logo/favicon, custom authentication flow, identification settings, stage order, and password/MFA policy wiring are shared. Only the domain and displayed titles become local Development values. Built-in stages and policies are discovered locally, and the existing local brand is moved in state rather than duplicated.

After Authentik configuration, from Istio apply the shared browser policies and ingress routes:

```bash
tests/kubernetes/apply-auth.sh
tests/kubernetes/apply-routes.sh
```

Then from agentgateway:

```bash
tests/kubernetes/setup.sh
```

This invokes its checked-out deployment and manifest modules in separate stages, not copied chart versions or a second proxy configuration.

Rerun the relevant component setup/apply after editing application configuration, then rerun verification without resetting the database. Do not switch to a released module pin that would omit local edits.

### Developer handoff

After setup, explicitly explain how to test a change:

- Edit checked-out code, including uncommitted changes. Rerun Authentik or agentgateway `tests/kubernetes/setup.sh` for changes to those component modules. For Istio runtime changes rerun setup; for shared browser-auth policies or local routes rerun `apply-auth.sh` or `apply-routes.sh`.
- Run the component verifiers and this skill's holistic HTTP verifier, then exercise the specific changed behavior through the browser URLs below. Check expected access and denial; healthy services alone do not verify the change.
- Do not tear down during normal iteration. Teardown deletes local users, memberships, and database data.
- Changes to Pneuma's `regional/authentik-config/authentication` brand, flow, stages, policies, or identification settings are exercised by rerunning Authentik setup and verification. Changes to the shared Istio browser-auth renderer are exercised by rerunning `apply-auth.sh`.
- Explain the fidelity boundary: authentication configuration and Istio browser-auth rendering are shared; local domains/titles, OAuth client/callback, application IDs, and explicit local groups substitute for cloud discovery. PostgreSQL, upstream images, local TLS, and Kind substitute for Cloud SQL, mirrored registries, cloud certificates, Workload Identity, and GCP networking. Cloud root discovery, environment enablement, and multi-region behavior still require sandbox verification.
- Local testing does not deploy sandbox or update released module pins. Use the normal PR/release process after local verification.

## Automated verification

From the skill directory, run the single verification entry point with the absolute aggregated-workspace root:

```bash
scripts/verify-stack.sh /absolute/path/to/platform-group
```

The runner invokes each component's `tests/kubernetes/verify.sh` from that component's checkout, then the holistic HTTP verifier, then the runtime security checks. It stops on the first failed stage, leaves the owned fixtures running, identifies the failed stage, and never tears down the stack as a fallback. Do not replace it with hand-built `kubectl`, `curl`, or metric commands.

For configuration-parity iterations, apply the edited configuration using its owning component script, then use the HTTP verifier's bounded expected-status mode to wait for gateway policy propagation. For example:

```bash
python3 scripts/verify-http.py --expect-status 302 --timeout 120 \
  https://dev.localhost/istio-test/metadata/cluster-name
```

Use the expected status for the specific temporary behavior, restore the intended configuration, reapply it, and wait for the original expected status the same way. A single immediate HTTP sample can race Istio propagation and is not evidence of either the temporary behavior or successful restoration.

Require:

- Ready Authentik/server/worker/database, Istio CNI/ztunnel, agentgateway/controller/proxy, and diagnostic workloads.
- The local hostname selects the shared brand/custom flow; live brand/CSS, identification settings, all four stage bindings, and both password/MFA policy bindings match the applied shared module. The test-only administrator must complete identification, password, and login and establish an authenticated session. This is not Google browser verification.
- Programmed gateways and Accepted/ResolvedRefs for each route's intended parent.
- Ambient workload/proxy enrollment, with no injected `istio-proxy` sidecars.
- Exactly `200` without redirects for public health and metadata endpoints on both paths.
- Exactly `302` to Authentik for protected paths, with the correct per-host outpost callback, both with and without forged identity headers.
- Outpost ping `204`, reachable callback routing, and the registered Google localhost callback.
- Authentik protection for the agentgateway admin UI.

The shared HTTP verifier uses loopback explicitly while preserving host/SNI, disables proxy use for local requests, and never follows protected redirects. Its expected-status mode polls only the allowlisted local HTTPS hostnames and reports the last observed status at timeout. It does not read credentials or store browser cookies.

The runtime verifier tests fail-closed behavior only on the owned fixture. It records the Authentik server's replica count, temporarily scales that deployment to zero, waits for endpoints to disappear, checks protected traffic is denied, restores the original count even after errors or termination signals, and waits up to three minutes for both ready endpoints and the protected route's HTTP 302 recovery. A restoration or recovery failure is a failed run, not a successful negative test; report that state plainly and do not continue to browser sign-in until the stack is healthy.

The runtime verifier also creates and removes a short-lived curl workload in the ambient `istio-test` namespace to exercise Agentgateway admin port `15000`. It requires a ztunnel `DENY` metric for that request; a TCP reset is an expected denial, not a failed HTTP status assertion. It inspects ztunnel metrics on every node hosting the relevant source or destination workload and requires positive counters with `connection_security_policy="mutual_tls"` for ingress-to-Agentgateway and Agentgateway-to-diagnostic traffic. Its output distinguishes each verified result from failures. The Agentgateway browser UI is `https://agentgateway.localhost/ui/`; never offer a direct port-forward as an authenticated UI path.

Do not report the fail-closed check as successful until Authentik restoration and HTTP 302 recovery have both been observed. If restoration fails, state that explicitly, do not proceed with remaining checks, and use the owning Authentik component verifier/setup script to diagnose and restore the owned fixture before retrying. Do not manually scale workloads with ad-hoc commands.

After traffic generation, inspect ztunnel metrics on every relevant node. Require `connection_security_policy="mutual_tls"` evidence for Istio ingress to agentgateway and agentgateway to the diagnostic workload. A single randomly chosen daemonset pod or absence of connection logs is insufficient.

## Browser verification

Leave the owned fixtures running and direct the developer to:

```text
https://dev.localhost/istio-test/auth
https://agentgateway.localhost/agentgateway-test/auth
https://agentgateway.localhost/ui/
```

Accept the temporary local certificate warning and sign in through Google. Both diagnostic paths must return the actual user's trusted `x-authentik-*` identity as JSON. Browser identity is conveyed by headers, not a bearer JWT.

Verify authenticated requests cannot override the actual user through forged identity headers. Remove the test user's required local group membership, require denial, then restore membership and verify recovery. Do not change Google/production groups or retain personal identity output in session artifacts.

If browser automation or the developer is unavailable, stop with **automated checks passed; Google browser verification pending**, not full success. That status is allowed only after the verification runner has exited successfully, including Authentik recovery, admin denial, and per-node mTLS checks. If any automated check or restoration failed, report that failure separately and do not say automated checks passed.

Demonstrate configuration parity by changing a relevant checked-out policy/configuration and observing the expected local behavior change, then restoring the intended configuration. A fixture that independently reproduces the old behavior is not enough.

## Diagnostics

| Failure | Inspect |
| --- | --- |
| Ownership guard rejects setup | Existing state and installations; preserve the old stack and resolve migration explicitly |
| Authentik bootstrap/API objects not ready | Kubernetes PostgreSQL/server/worker status and redacted logs |
| Ambient enrollment fails | Kind provisioner, mount propagation, CNI and ztunnel logs |
| Public endpoints redirect or protected requests bypass sign-in | Shared authorization inputs, gateway policies, inbound header stripping, ingress logs |
| Agentgateway route/proxy fails | Chart availability, staged CRDs, intended route-parent conditions, ReferenceGrant and proxy/controller logs |
| Browser callback fails | Registered Google localhost URI, Host rewrite, callback redirect, Authentik session host |
| In-mesh traffic resets or returns 503 | Workload endpoints, ztunnel identities, mTLS metrics and certificate readiness |

Use bounded waits. Do not downgrade Istio or agentgateway to sidestep incompatibilities; report a blocked version with evidence. Local success does not validate GCP load balancing, Cloud Armor, Workload Identity, Cloud SQL, multi-region behavior, or the complete sandbox deployment.

## Cleanup

Cleanup is explicit and owned-resource-only. It deletes all fixture namespaces, including local users and PostgreSQL data. Stop agentgateway first, then Authentik, then Istio:

```bash
# In each owning repository:
tests/kubernetes/teardown.sh
```

Teardown removes `agentgateway`, `authentik`, `istio-system`, `istio-ingress`, and `istio-test` after checking fixture ownership. Authentik clears application configuration state after deleting its namespace and database volume so the next setup imports newly bootstrapped objects rather than using stale IDs. Generated local credentials remain in `.work/`, but users, memberships, and application data are recreated on the next setup. No separate reset command is needed. Rerunning setup without teardown still preserves the running database for iteration.

Agentgateway's local CRD chart uses a Bash post-renderer with `jq` that invokes `kubectl --local` and preserves each manifest's document boundary while adding Helm's `keep` resource policy. This retains its cluster-wide CRDs when the component's release and namespace are destroyed; ordinary cloud deployment defaults are unchanged.

Do not remove cluster-wide CRDs or unowned installations. Report retained namespaces, data, runtime components, and owned helper processes accurately.
