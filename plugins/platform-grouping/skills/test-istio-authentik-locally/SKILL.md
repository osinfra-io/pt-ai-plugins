---
name: test-istio-authentik-locally
description: Set up, test, debug, and tear down the local Authentik and Istio browser-authentication flow on an ambient-only Istio mesh with Docker Desktop Kubernetes (Kind provisioner). Optionally layers AgentGateway behind Istio. Use when asked to run or troubleshoot local Istio, Authentik, AgentGateway, forward-auth, ext_authz, or browser authentication tests in the osinfra-io platform repositories.
---

# Test Istio and Authentik locally

Execute the local browser-authentication test autonomously against an ambient-only mesh (`istiod`, `istio-cni`, `ztunnel`; no sidecars), matching production. Diagnose and fix setup failures rather than only printing commands. Stop before the interactive sign-in when no browser automation is available, report the exact URL to open, and leave the fixtures running unless the user asks for cleanup.

## Repository discovery

Locate these checkouts without assuming the current directory:

- `pt-arche-kubernetes-authentik`
- `pt-arche-kubernetes-istio`
- `pt-pneuma-istio-test`
- `pt-arche-kubernetes-agentgateway` (AgentGateway layer)

In the aggregated `platform-group` workspace they are under `arche/`, `arche/`, `pneuma/`, and `arche/` respectively. Otherwise, search the current directory and its descendants while excluding `.terraform/`. Record absolute paths and run every command from the repository it belongs to.

Run the AgentGateway layer whenever its checkout is found or the user asks about AgentGateway; set up in Authentik -> Istio -> AgentGateway order and clean up in reverse.

Read each repository's `.github/copilot-instructions.md` and the Arche team instructions before changing files.

## Prerequisites

Verify before changing the running environment:

```bash
command -v curl docker helm kubectl openssl tofu
docker info
kubectl config current-context
kubectl cluster-info
```

Require a running Docker daemon and the `docker-desktop` Kubernetes context. Do not silently switch from another Kubernetes context; stop and explain the safety issue instead.

Docker Desktop Kubernetes must use the **Kind** provisioner (Settings > Kubernetes > Cluster provisioning method), allocated at least 4 CPUs and 8 GB of memory. The legacy **kubeadm** provisioner runs Kubernetes in Docker Desktop's VM, whose root mount is not shared, so the ambient `istio-cni` agent fails with `path /var/run/netns is mounted on /run but it is not a shared or slave mount` ([docker/desktop-feedback#629](https://github.com/docker/desktop-feedback/issues/629), [istio/istio#47436](https://github.com/istio/istio/issues/47436)). Kind nodes run as containers with shared mount propagation, so ambient works there. `tests/docker/setup.sh` rejects non-Kind nodes and unsuitable mount propagation; if it does, tell the user to switch the provisioner rather than falling back to sidecar mode.

The interactive browser test uses Google sign-in. Preserve existing `TF_VAR_google_oauth_client_id` and `TF_VAR_google_oauth_client_secret` values; never print either value. If they are unavailable, stop after the HTTP redirect checks and report that interactive Google authentication cannot be completed. The Google OAuth web client must allow this redirect URI:

```text
http://localhost:9000/source/oauth/callback/google/
```

## Start and configure Authentik

From `pt-arche-kubernetes-authentik`:

```bash
docker compose --env-file tests/docker/.env --file tests/docker/compose.yml up --detach
tests/docker/wait-for-authentik.sh
tofu -chdir=tests/docker/regional/config init
tofu -chdir=tests/docker/regional/config apply -auto-approve
```

If a command fails, inspect `docker compose --env-file tests/docker/.env --file tests/docker/compose.yml ps` and `docker compose --env-file tests/docker/.env --file tests/docker/compose.yml logs --tail=200 server worker postgresql`. Confirm Authentik health before continuing:

```bash
curl --fail --insecure --silent --show-error https://127.0.0.1:9443/-/health/live/
```

The fixture must configure the embedded outpost browser URL as `http://localhost:9000`; the OpenTofu provider still connects through `https://127.0.0.1:9443`.

`AUTHENTIK_SECRET_KEY` must differ from `AUTHENTIK_BOOTSTRAP_TOKEN` in `tests/docker/.env`. The embedded outpost authenticates with the secret key, and if it matches an API token the request runs as `akadmin`, so `/api/v3/outposts/proxy/` returns `403` (`failed to fetch providers` in server logs) and every protected path returns `404`.

## Install the Istio fixture

From `pt-arche-kubernetes-istio`:

```bash
tests/docker/setup.sh
```

The script locates `pt-pneuma-istio-test` automatically in standard checkout layouts. Set `ISTIO_TEST_CONTEXT` to its absolute path only if automatic discovery fails. It installs Istio with the `ambient` profile, labels `istio-test` with `istio.io/dataplane-mode: ambient`, waits for the `istio-cni-node` and `ztunnel` DaemonSets, and fails if a workload pod is not ambient-enrolled or contains an `istio-proxy` container.

Verify the resulting resources:

```bash
kubectl wait --for=condition=Programmed gateway/gateway --namespace=istio-ingress --timeout=120s
kubectl rollout status daemonset/istio-cni-node --namespace=istio-system --timeout=180s
kubectl rollout status daemonset/ztunnel --namespace=istio-system --timeout=180s
kubectl rollout status deployment/istio-test --namespace=istio-test --timeout=180s
kubectl get gateway,httproute,authorizationpolicy --all-namespaces
kubectl get pods --namespace=istio-test --output=custom-columns='POD:.metadata.name,CONTAINERS:.spec.containers[*].name,AMBIENT:.metadata.annotations.ambient\.istio\.io/redirection'
```

Every `istio-test` pod must list only its application container and show `AMBIENT` as `enabled`.

If setup fails, inspect the gateway, route, and policy, then use ambient diagnostics rather than sidecar ones:

- `kubectl logs --namespace=istio-system daemonset/istio-cni-node --tail=100` for CNI install or pod redirection failures;
- `kubectl logs --namespace=istio-system daemonset/ztunnel --tail=100` for HBONE connections, workload identities (`src.identity`), and mTLS errors;
- `kubectl logs --namespace=istio-ingress deployment/gateway-istio --tail=100` for ingress routing and `ext_authz` decisions.

Do not read or search `.terraform/` directories.

## Verify public bypasses

Request the public health and metadata endpoints without following redirects:

```bash
curl --insecure --silent --show-error --dump-header - --output /dev/null https://dev.localhost/istio-test/health
curl --insecure --silent --show-error --dump-header - --output /dev/null https://dev.localhost/istio-test/metadata/cluster-name
```

Require both responses to return `200` without a `Location` header pointing to Authentik. These endpoints are public diagnostics; an Authentik redirect means the public-path bypass is not working.

## Verify forward authentication

Request the protected identity diagnostic without following redirects:

```bash
curl --insecure --silent --show-error --dump-header - --output /dev/null https://dev.localhost/istio-test/auth
```

Require all of the following:

- status `302`;
- `Location` begins with `http://localhost:9000/application/o/authorize/`;
- the encoded callback points to `https://dev.localhost/outpost.goauthentik.io/callback`.

Then follow redirects to verify that the Authentik login flow is reachable:

```bash
curl --insecure --location --silent --show-error --output /dev/null --write-out '%{http_code}\n' https://dev.localhost/istio-test/auth
```

The final status must be `200`. A redirect to `http://localhost/` without port `9000` indicates that the embedded outpost's `authentik_host` is stale or unset.

## Install and verify the AgentGateway layer

From `pt-arche-kubernetes-agentgateway`, after the Istio checks above pass:

```bash
tests/docker/setup.sh
```

The script pins the AgentGateway Helm charts (`AGENTGATEWAY_VERSION`), enrolls `agentgateway-system` in ambient mode, and applies the internal proxy `Gateway`, `AgentgatewayParameters`, ingress and backend `HTTPRoute`s, the `ReferenceGrant` in `istio-test`, and an Authentik `CUSTOM` `AuthorizationPolicy` for `/agentgateway-test`. It fails unless the controller and proxy roll out, the proxy is ambient-enrolled with no `istio-proxy`, the Gateway is `Programmed`, both routes are `Accepted` and `ResolvedRefs`, `/agentgateway-test/health` and `/agentgateway-test/metadata/cluster-name` return `200`, `/agentgateway-test/auth` redirects to Authentik with and without spoofed `X-Authentik-*` headers, and the admin UI at `/ui/` redirects to Authentik. On failure it prints Helm releases, CRDs, Gateway and route status, the `ReferenceGrant`, pods, controller/proxy logs, and ztunnel logs.

Before changing the pinned version, resolve the latest stable release with `gh release list --repo agentgateway/agentgateway --exclude-pre-releases --limit 1`. Never downgrade Istio or select an older AgentGateway release to make the test pass; record an incompatibility as blocked with a minimal reproduction and an upstream issue instead.

Confirm the in-mesh hops are mutual TLS through ztunnel. The proxy pools connections, so use ztunnel metrics rather than access logs:

```bash
kubectl port-forward --namespace=istio-system daemonset/ztunnel 15020:15020
curl --silent http://localhost:15020/metrics | grep '^istio_tcp_connections_opened_total' | grep agentgateway-proxy
```

Expect `connection_security_policy="mutual_tls"` series for `gateway-istio` -> `agentgateway-proxy` and `agentgateway-proxy` -> `istio-test`. Stop the port-forward afterwards.

## Identify the failing layer

| Symptom | Owning layer | Inspect |
| --- | --- | --- |
| Protected path returns `404` before any redirect; `failed to fetch providers` in server logs | Authentik | `docker compose ... logs --tail=200 server`; secret key vs bootstrap token |
| `istio-cni-node` or `ztunnel` not ready; pod missing `ambient.istio.io/redirection` | Istio ambient | `istio-cni-node` and `ztunnel` logs; Kind provisioner and mount propagation |
| Public path redirects to Authentik, or protected path returns `200` without sign-in | Istio authorization | `AuthorizationPolicy` paths/`notPaths`; `gateway-istio` logs |
| `Programmed`, `Accepted`, or `ResolvedRefs` not `True`; `5xx` only on `/agentgateway-test` | AgentGateway | `helm list -n agentgateway-system`; `kubectl get crd \| grep agentgateway.dev`; route status; `agentgateway` and `agentgateway-proxy` logs; `ReferenceGrant` |
| Connection resets between gateways and workloads | ztunnel/mTLS | ztunnel logs and `istio_tcp_connections_opened_total` |
| Controller logs reject Istio resources or versions | AgentGateway/Istio compatibility | Release notes and upstream issues for the pinned versions |

## Complete the browser test

Tell the user to open:

```text
https://dev.localhost/istio-test/auth
```

When the AgentGateway layer is installed, also open `https://dev.localhost/agentgateway-test/auth`; success returns the same identity diagnostic through AgentGateway. The AgentGateway admin UI is at `https://dev.localhost/ui/` behind the same Authentik sign-in. Never offer `kubectl port-forward` to proxy port `15000` as the UI URL: it bypasses Authentik. In-mesh access to port `15000` from anything other than the Istio ingress gateway is denied by the `agentgateway-admin` ztunnel policy. They must accept the temporary self-signed certificate warning. Select Google and authenticate with an allowed Workspace account. Success returns a JSON diagnostic showing the trusted `x-authentik-*` identity headers that Authentik forwarded to the workload. Browser identity reaches the workload through these headers rather than a JWT. After the browser test, confirm the in-mesh hop was carried by ztunnel: `kubectl logs --namespace=istio-system daemonset/ztunnel --since=5m | grep istio-test` should show `connection complete` entries with `src.identity="spiffe://cluster.local/ns/istio-test/sa/default"`. Do not claim interactive end-to-end success unless the browser callback has actually completed.

## Cleanup

Only tear down when requested. If the AgentGateway layer is installed, first run from `pt-arche-kubernetes-agentgateway`:

```bash
tests/docker/teardown.sh
```

It deletes the fixture manifests, both Helm releases, the AgentGateway CRDs, the controller-created `GatewayClass`, and `agentgateway-system`, then fails if any AgentGateway resources remain.

Then from `pt-arche-kubernetes-istio`:

```bash
tests/docker/teardown.sh
```

This deletes the test namespaces, purges `istiod`, `istio-cni`, `ztunnel`, and the ingress gateway with `istioctl uninstall --purge`, and removes the Gateway API CRDs. The `istio-test:local` image remains in the Kind node's containerd store.

Then from `pt-arche-kubernetes-authentik`:

```bash
tofu -chdir=tests/docker/regional/config destroy -auto-approve
docker compose --env-file tests/docker/.env --file tests/docker/compose.yml down --volumes
```

Report which fixtures remain running when cleanup is skipped.
