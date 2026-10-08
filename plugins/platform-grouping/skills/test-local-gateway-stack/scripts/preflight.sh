#!/usr/bin/env bash

set -euo pipefail

for tool in curl docker helm jq kubectl openssl python3 tofu; do
  if ! command -v "${tool}" >/dev/null; then
    echo "Missing local integration prerequisite: ${tool}" >&2
    exit 1
  fi
done
docker info >/dev/null

if [ "$(kubectl config current-context)" != "docker-desktop" ]; then
  echo "Select the dedicated docker-desktop context explicitly; this script will not switch contexts." >&2
  exit 1
fi
kubectl --context=docker-desktop --request-timeout=15s get --raw=/readyz >/dev/null
nodes="$(kubectl --context=docker-desktop get nodes --output=jsonpath='{.items[*].metadata.name}')"
if [ -z "${nodes}" ]; then
  echo "Docker Desktop Kubernetes has no nodes." >&2
  exit 1
fi
for node in ${nodes}; do
  if [ "$(docker inspect "${node}" --format '{{index .Config.Labels "io.x-k8s.kind.cluster"}}')" != "desktop" ]; then
    echo "Docker Desktop must use its Kind provisioner, not kubeadm." >&2
    exit 1
  fi
  propagation="$(docker exec "${node}" findmnt --noheadings --target /var/run/netns --output PROPAGATION)"
  case "${propagation}" in
    *shared* | *slave*) ;;
    *)
      echo "Node ${node} does not support ambient CNI mount propagation (${propagation})." >&2
      exit 1
      ;;
  esac
done

if kubectl --context=docker-desktop get configmap local-gateway-stack-owner --namespace=kube-system >/dev/null 2>&1; then
  if [ "$(kubectl --context=docker-desktop get configmap local-gateway-stack-owner --namespace=kube-system --output=jsonpath='{.data.owner}')" != "osinfra-local-gateway-stack" ]; then
    echo "The cluster ownership marker belongs to another owner." >&2
    exit 1
  fi
  echo "Docker Desktop Kind prerequisites and fixture ownership checks passed."
  exit 0
fi

if [ "${1:-}" != "--claim" ]; then
  echo "No ownership marker. Run preflight.sh --claim only on an empty dedicated test cluster." >&2
  exit 1
fi
namespaces="$(kubectl --context=docker-desktop get namespaces --output=jsonpath='{.items[*].metadata.name}')"
for namespace in ${namespaces}; do
  case "${namespace}" in
    default | kube-system | kube-public | kube-node-lease | local-path-storage) ;;
    *)
      echo "Existing namespace ${namespace} has no fixture ownership record; refusing to adopt or overwrite it." >&2
      exit 1
      ;;
  esac
done
if [ -n "$(helm --kube-context=docker-desktop list --all-namespaces --all --short)" ]; then
  echo "Existing Helm installations prevent claiming this cluster." >&2
  exit 1
fi
existing_crds="$(kubectl --context=docker-desktop get crds --output=name)"
if grep --quiet -E '\.(gateway\.networking\.k8s\.io|agentgateway\.dev|istio\.io)$' <<<"${existing_crds}"; then
  echo "Existing gateway/mesh CRDs prevent claiming this cluster; do not purge them automatically." >&2
  exit 1
fi
kubectl --context=docker-desktop create configmap local-gateway-stack-owner \
  --namespace=kube-system --from-literal=owner=osinfra-local-gateway-stack
echo "Dedicated local cluster claimed. Component setup must still validate its own local state."
