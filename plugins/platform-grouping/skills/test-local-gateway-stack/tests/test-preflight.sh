#!/usr/bin/env bash

set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly SKILL_DIR
TEST_DIR="$(mktemp -d)"
readonly TEST_DIR
trap 'rm -f "${TEST_DIR}/claimed" "${TEST_DIR}/output"; rmdir "${TEST_DIR}"' EXIT
export CLAIM_FILE="${TEST_DIR}/claimed"

docker() {
  case "$1" in
    info) ;;
    inspect) echo desktop ;;
    exec) echo shared ;;
    *) return 1 ;;
  esac
}

kubectl() {
  case "$*" in
    "config current-context") echo docker-desktop ;;
    *"get --raw=/readyz") ;;
    *"get nodes "*) echo desktop-control-plane ;;
    *"get configmap "*) return 1 ;;
    *"get namespaces "*) echo "default kube-system" ;;
    *"get crds "*) ;;
    *"create configmap "*) touch "${CLAIM_FILE}" ;;
    *) return 1 ;;
  esac
}

helm() {
  [ "$*" = "--kube-context=docker-desktop list --all-namespaces --all --short" ] || return 1
  if [ "${PENDING_RELEASE}" = yes ]; then
    echo pending-release
  fi
}
export -f docker kubectl helm

export PENDING_RELEASE=yes
if bash "${SKILL_DIR}/scripts/preflight.sh" --claim >"${TEST_DIR}/output" 2>&1; then
  echo "Expected pending release to prevent claiming" >&2
  exit 1
fi
grep -Fq "Existing Helm installations prevent claiming this cluster." "${TEST_DIR}/output"
[ ! -e "${CLAIM_FILE}" ]

export PENDING_RELEASE=no
bash "${SKILL_DIR}/scripts/preflight.sh" --claim >"${TEST_DIR}/output" 2>&1
[ -f "${CLAIM_FILE}" ]
echo "Preflight pending-release ownership tests passed."
