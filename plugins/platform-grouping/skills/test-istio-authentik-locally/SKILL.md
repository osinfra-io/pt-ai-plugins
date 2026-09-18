---
name: test-istio-authentik-locally
description: Set up, test, debug, and tear down the local Authentik and Istio browser-authentication flow with Docker Desktop Kubernetes. Use when asked to run or troubleshoot local Istio, Authentik, forward-auth, ext_authz, or browser authentication tests in the osinfra-io platform repositories.
---

# Test Istio and Authentik locally

Execute the local browser-authentication test autonomously. Diagnose and fix setup failures rather than only printing commands. Stop before the interactive sign-in when no browser automation is available, report the exact URL to open, and leave the fixtures running unless the user asks for cleanup.

## Repository discovery

Locate these checkouts without assuming the current directory:

- `pt-arche-kubernetes-authentik`
- `pt-arche-kubernetes-istio`
- `pt-pneuma-istio-test`

In the aggregated `platform-group` workspace they are under `arche/`, `arche/`, and `pneuma/` respectively. Otherwise, search the current directory and its descendants while excluding `.terraform/`. Record absolute paths and run every command from the repository it belongs to.

Read each repository's `.github/copilot-instructions.md` and the Arche team instructions before changing files.

## Prerequisites

Verify before changing the running environment:

```bash
command -v curl docker kubectl openssl tofu
docker info
kubectl config current-context
kubectl cluster-info
```

Require a running Docker daemon and the `docker-desktop` Kubernetes context. Do not silently switch from another Kubernetes context; stop and explain the safety issue instead.

The local test works with the committed bootstrap account and does not require Google credentials. To test Google sign-in, preserve existing `TF_VAR_google_oauth_client_id` and `TF_VAR_google_oauth_client_secret` values. Never print either value. The Google OAuth web client must allow this redirect URI:

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

## Install the Istio fixture

From `pt-arche-kubernetes-istio`:

```bash
tests/docker/setup.sh
```

The script locates `pt-pneuma-istio-test` automatically in standard checkout layouts. Set `ISTIO_TEST_CONTEXT` to its absolute path only if automatic discovery fails.

Verify the resulting resources:

```bash
kubectl wait --for=condition=Programmed gateway/gateway --namespace=istio-ingress --timeout=120s
kubectl rollout status deployment/istio-test --namespace=istio-test --timeout=180s
kubectl get gateway,httproute,authorizationpolicy --all-namespaces
```

If setup fails, inspect the gateway, route, policy, pod, and recent proxy logs. Do not read or search `.terraform/` directories.

## Verify forward authentication

Request the protected endpoint without following redirects:

```bash
curl --insecure --silent --show-error --dump-header - --output /dev/null https://dev.localhost/istio-test/health/basic
```

Require all of the following:

- status `302`;
- `Location` begins with `http://localhost:9000/application/o/authorize/`;
- the encoded callback points to `https://dev.localhost/outpost.goauthentik.io/callback`.

Then follow redirects to verify that the Authentik login flow is reachable:

```bash
curl --insecure --location --silent --show-error --output /dev/null --write-out '%{http_code}\n' https://dev.localhost/istio-test/health/basic
```

The final status must be `200`. A redirect to `http://localhost/` without port `9000` indicates that the embedded outpost's `authentik_host` is stale or unset.

## Complete the browser test

Tell the user to open:

```text
https://dev.localhost/istio-test/health/basic
```

They must accept the temporary self-signed certificate warning. Without Google credentials, use the committed local fixture account:

```text
Username: akadmin
Password: not-a-secret
```

With Google credentials configured, select Google and authenticate with an allowed Workspace account. Success returns the `istio-test` health response. Do not claim interactive end-to-end success unless the browser callback has actually completed.

## Cleanup

Only tear down when requested. From `pt-arche-kubernetes-istio`:

```bash
tests/docker/teardown.sh
```

Then from `pt-arche-kubernetes-authentik`:

```bash
tofu -chdir=tests/docker/regional/config destroy -auto-approve
docker compose --env-file tests/docker/.env --file tests/docker/compose.yml down --volumes
```

Report which fixtures remain running when cleanup is skipped.
