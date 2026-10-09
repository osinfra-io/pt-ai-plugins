#!/usr/bin/env bash

set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ "$#" -ne 1 ]; then
  echo "Usage: verify-stack.sh <platform-group workspace root>" >&2
  exit 2
fi

WORKSPACE_ROOT="$(cd "$1" && pwd)"
readonly WORKSPACE_ROOT

readonly AUTHENTIK_REPO="${WORKSPACE_ROOT}/arche/pt-arche-kubernetes-authentik"
readonly ISTIO_REPO="${WORKSPACE_ROOT}/arche/pt-arche-kubernetes-istio"
readonly AGENTGATEWAY_REPO="${WORKSPACE_ROOT}/arche/pt-arche-kubernetes-agentgateway"

for repo in "${AUTHENTIK_REPO}" "${ISTIO_REPO}" "${AGENTGATEWAY_REPO}"; do
  if [ ! -x "${repo}/tests/kubernetes/verify.sh" ]; then
    echo "Missing executable component verifier: ${repo}/tests/kubernetes/verify.sh" >&2
    exit 1
  fi
done

run_component_verifier() {
  local name="$1"
  local repo="$2"

  echo "==> Verifying ${name} from ${repo}"
  if ! (cd "${repo}" && tests/kubernetes/verify.sh); then
    echo "FAILED: ${name} component verification. Fixtures were not torn down." >&2
    exit 1
  fi
}

run_component_verifier "Istio" "${ISTIO_REPO}"
run_component_verifier "Authentik" "${AUTHENTIK_REPO}"
run_component_verifier "Agentgateway" "${AGENTGATEWAY_REPO}"

echo "==> Running holistic anonymous HTTP verification"
if ! python3 "${SCRIPT_DIR}/verify-http.py"; then
  echo "FAILED: holistic HTTP verification. Fixtures were not torn down." >&2
  exit 1
fi

echo "==> Running fail-closed, in-mesh admin-denial, and ztunnel mTLS verification"
if ! python3 "${SCRIPT_DIR}/verify-runtime.py"; then
  echo "FAILED: runtime security verification. Check that Authentik was restored before retrying. Fixtures were not torn down." >&2
  exit 1
fi

echo "Automated gateway-stack checks passed. Google browser sign-in and authenticated identity verification remain pending."
