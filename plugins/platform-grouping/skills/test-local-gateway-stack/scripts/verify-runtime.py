#!/usr/bin/env python3
"""Verify owned gateway runtime behavior and restore temporary fixture changes."""

import json
import re
import signal
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass


CONTEXT = "docker-desktop"
OWNER_NAMESPACE = "kube-system"
OWNER_CONFIGMAP = "local-gateway-stack-owner"
OWNER_VALUE = "osinfra-local-gateway-stack"
AUTHENTIK_NAMESPACE = "authentik"
AUTHENTIK_DEPLOYMENT = "authentik-server"
AUTHENTIK_SERVICE = "authentik-server"
PROTECTED_URL = "https://dev.localhost/istio-test/auth"
ADMIN_NAMESPACE = "agentgateway"
ADMIN_SERVICE = "agentgateway-proxy-admin"
ADMIN_URL = f"http://{ADMIN_SERVICE}.{ADMIN_NAMESPACE}.svc.cluster.local:15000/ui/"
ADMIN_CLIENT_NAMESPACE = "istio-test"
ADMIN_CLIENT_IMAGE = "curlimages/curl:8.16.0"
POLL_INTERVAL_SECONDS = 2
RECOVERY_TIMEOUT_SECONDS = 180
OUTAGE_TIMEOUT_SECONDS = 90
METRIC_RE = re.compile(r"([a-zA-Z_][a-zA-Z0-9_]*)=\"((?:\\\\.|[^\"])*)\"")


class VerificationError(RuntimeError):
    pass


@dataclass(frozen=True)
class MetricSample:
    name: str
    labels: dict
    value: float


def run_command(command, timeout=30):
    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise VerificationError(f"Command could not complete: {command[0]}") from error
    if result.returncode:
        raise VerificationError(f"Command failed: {' '.join(command[:3])}")
    return result.stdout.strip()


def kubectl(*args, timeout=30):
    return run_command(["kubectl", f"--context={CONTEXT}", *args], timeout=timeout)


def check_owner():
    context = run_command(["kubectl", "config", "current-context"])
    if context != CONTEXT:
        raise VerificationError(f"Current Kubernetes context is {context!r}, not {CONTEXT!r}.")
    owner = kubectl(
        "get",
        "configmap",
        OWNER_CONFIGMAP,
        f"--namespace={OWNER_NAMESPACE}",
        "--output=jsonpath={.data.owner}",
    )
    if owner != OWNER_VALUE:
        raise VerificationError("The local gateway fixture ownership marker does not match.")


def parse_positive_replicas(value):
    try:
        replicas = int(value)
    except ValueError as error:
        raise VerificationError("Authentik server replica count is not an integer.") from error
    if replicas < 1:
        raise VerificationError("Authentik server is already scaled to zero; refusing the fail-closed disruption test.")
    return replicas


def curl_status(url):
    command = [
        "curl",
        "--noproxy",
        "*",
        "--connect-timeout",
        "5",
        "--max-time",
        "15",
        "--insecure",
        "--silent",
        "--output",
        "/dev/null",
        "--write-out",
        "%{http_code}",
        url,
    ]
    try:
        result = subprocess.run(command, check=False, capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        return "000", 1
    return result.stdout.strip() or "000", result.returncode


def wait_for_endpoint_presence(present, timeout):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        addresses = kubectl(
            "get",
            "endpoints",
            AUTHENTIK_SERVICE,
            f"--namespace={AUTHENTIK_NAMESPACE}",
            "--output=jsonpath={.subsets[*].addresses[*].ip}",
        )
        if bool(addresses) == present:
            return
        time.sleep(min(POLL_INTERVAL_SECONDS, max(0, deadline - time.monotonic())))
    expected = "ready" if present else "absent"
    raise VerificationError(f"Timed out waiting for Authentik server endpoints to become {expected}.")


def wait_for_protected_recovery(timeout=RECOVERY_TIMEOUT_SECONDS):
    deadline = time.monotonic() + timeout
    last_status = "no response"
    while time.monotonic() < deadline:
        status, _ = curl_status(PROTECTED_URL)
        last_status = status
        if status == "302":
            return
        time.sleep(min(POLL_INTERVAL_SECONDS, max(0, deadline - time.monotonic())))
    raise VerificationError(
        f"Authentik was restored, but protected traffic did not recover to HTTP 302 "
        f"within {timeout}s (last observed HTTP {last_status})."
    )


def verify_fail_closed():
    check_owner()
    replicas = parse_positive_replicas(
        kubectl(
            "get",
            "deployment",
            AUTHENTIK_DEPLOYMENT,
            f"--namespace={AUTHENTIK_NAMESPACE}",
            "--output=jsonpath={.spec.replicas}",
        )
    )
    scaled_down = False
    outage_status = None
    check_error = None
    restore_error = None

    try:
        scaled_down = True
        kubectl(
            "scale",
            f"deployment/{AUTHENTIK_DEPLOYMENT}",
            f"--namespace={AUTHENTIK_NAMESPACE}",
            "--replicas=0",
        )
        kubectl(
            "rollout",
            "status",
            f"deployment/{AUTHENTIK_DEPLOYMENT}",
            f"--namespace={AUTHENTIK_NAMESPACE}",
            "--timeout=180s",
            timeout=190,
        )
        wait_for_endpoint_presence(False, OUTAGE_TIMEOUT_SECONDS)
        outage_status, curl_exit = curl_status(PROTECTED_URL)
        if outage_status != "403" and not (outage_status == "000" and curl_exit != 0):
            raise VerificationError(
                f"Fail-closed check expected HTTP 403 or a denied connection during Authentik outage; "
                f"observed HTTP {outage_status}."
            )
    except BaseException as error:
        check_error = error
    finally:
        if scaled_down:
            try:
                kubectl(
                    "scale",
                    f"deployment/{AUTHENTIK_DEPLOYMENT}",
                    f"--namespace={AUTHENTIK_NAMESPACE}",
                    f"--replicas={replicas}",
                    timeout=30,
                )
                kubectl(
                    "rollout",
                    "status",
                    f"deployment/{AUTHENTIK_DEPLOYMENT}",
                    f"--namespace={AUTHENTIK_NAMESPACE}",
                    "--timeout=180s",
                    timeout=190,
                )
                wait_for_endpoint_presence(True, RECOVERY_TIMEOUT_SECONDS)
                wait_for_protected_recovery()
            except BaseException as error:
                restore_error = error

    if restore_error:
        if check_error:
            raise VerificationError(
                f"Fail-closed check failed ({check_error}); Authentik restoration/recovery also failed "
                f"({restore_error}). Do not report automated success."
            ) from restore_error
        raise VerificationError(
            f"Fail-closed check completed, but Authentik restoration/recovery failed ({restore_error}). "
            "Do not report automated success."
        ) from restore_error
    if check_error:
        raise check_error

    print(f"PASS fail-closed: protected request denied with HTTP {outage_status} while Authentik was stopped.")
    print("PASS recovery: Authentik restored and protected traffic returned HTTP 302.")


def get_pods(namespace, selector):
    raw = kubectl(
        "get",
        "pods",
        f"--namespace={namespace}",
        f"--selector={selector}",
        "--output=json",
    )
    try:
        pods = json.loads(raw)["items"]
    except (json.JSONDecodeError, KeyError, TypeError) as error:
        raise VerificationError(f"Could not read pod placement in namespace {namespace}.") from error
    return [
        {"name": pod["metadata"]["name"], "node": pod["spec"].get("nodeName", "")}
        for pod in pods
        if pod.get("metadata", {}).get("name")
    ]


def require_pods(namespace, selector, description):
    pods = get_pods(namespace, selector)
    if not pods or any(not pod["node"] for pod in pods):
        raise VerificationError(f"Could not identify ready node placement for {description}.")
    return pods


def parse_metrics(text):
    samples = []
    for line in text.splitlines():
        if not line or line.startswith("#"):
            continue
        metric, separator, value = line.partition(" ")
        if not separator or "{" not in metric or not metric.endswith("}"):
            continue
        name, labels_text = metric.split("{", 1)
        try:
            labels = dict(METRIC_RE.findall(labels_text[:-1]))
            sample_value = float(value.strip())
        except ValueError:
            continue
        samples.append(MetricSample(name, labels, sample_value))
    return samples


def has_mtls_evidence(samples, source_workload, destination_workload, destination_namespace, service_name=None, denied=False):
    positive_metrics = {
        "istio_tcp_connections_opened_total",
        "istio_tcp_connections_closed_total",
        "istio_tcp_sent_bytes_total",
        "istio_tcp_received_bytes_total",
    }
    for sample in samples:
        labels = sample.labels
        if (
            sample.value <= 0
            or labels.get("source_workload") != source_workload
            or labels.get("destination_workload") != destination_workload
            or labels.get("destination_service_namespace") != destination_namespace
            or labels.get("connection_security_policy") != "mutual_tls"
        ):
            continue
        if service_name is not None and labels.get("destination_service_name") != service_name:
            continue
        if denied:
            if sample.name in ("istio_tcp_connections_closed_total", "istio_tcp_connections_failed_total") and labels.get(
                "response_flags"
            ) == "DENY":
                return True
        elif sample.name in positive_metrics:
            return True
    return False


def get_ztunnel_metrics_by_node():
    pods = require_pods("istio-system", "app=ztunnel", "ztunnel")
    metrics = {}
    for pod in pods:
        path = f"/api/v1/namespaces/istio-system/pods/{pod['name']}:15020/proxy/metrics"
        metrics[pod["node"]] = parse_metrics(kubectl("get", "--raw", path, timeout=30))
    return metrics


def require_flow_on_relevant_nodes(metrics_by_node, source_pods, destination_pods, description, **criteria):
    nodes = sorted({pod["node"] for pod in source_pods + destination_pods})
    for node in nodes:
        samples = metrics_by_node.get(node)
        if samples is None:
            raise VerificationError(f"No ztunnel metrics were collected from relevant node {node} for {description}.")
        if not has_mtls_evidence(samples, **criteria):
            raise VerificationError(f"No required mutual-TLS metric evidence on node {node} for {description}.")
    print(f"PASS ztunnel mTLS: {description} observed on every relevant node ({', '.join(nodes)}).")


def verify_admin_denial(metrics_by_node, client_pod):
    output = kubectl("logs", client_pod["name"], f"--namespace={ADMIN_CLIENT_NAMESPACE}")
    match = re.search(r"curl_exit=(\d+) http_status=(\d{3})", output)
    if not match:
        raise VerificationError("The in-mesh admin probe did not produce a valid HTTP result.")
    curl_exit, status = int(match.group(1)), match.group(2)
    if status in ("000",) and curl_exit == 0:
        raise VerificationError("The in-mesh admin probe reported a connection failure without a curl error.")
    if status.startswith(("2", "3")):
        raise VerificationError(f"Unauthorized in-mesh request to admin port 15000 returned HTTP {status}.")

    proxy_pods = require_pods(
        ADMIN_NAMESPACE,
        "gateway.networking.k8s.io/gateway-name=agentgateway-proxy",
        "Agentgateway proxy",
    )
    require_flow_on_relevant_nodes(
        metrics_by_node,
        [client_pod],
        proxy_pods,
        "unauthorized in-mesh request to admin port 15000 was denied",
        source_workload=client_pod["name"],
        destination_workload="agentgateway-proxy",
        destination_namespace=ADMIN_NAMESPACE,
        service_name=ADMIN_SERVICE,
        denied=True,
    )
    print(f"PASS admin denial: unauthorized ambient request denied (HTTP {status}, curl exit {curl_exit}).")


def run_admin_probe():
    namespace = kubectl(
        "get",
        "namespace",
        ADMIN_CLIENT_NAMESPACE,
        "--output=jsonpath={.metadata.labels.istio\\.io/dataplane-mode}",
    )
    if namespace != "ambient":
        raise VerificationError("The diagnostic namespace is not enrolled in ambient mode; refusing a sidecar fallback.")

    pod_name = f"unauthorized-admin-check-{uuid.uuid4().hex[:8]}"
    script = (
        f'if status="$(curl --noproxy "*" --connect-timeout 5 --max-time 10 --silent '
        f'--output /dev/null --write-out "%{{http_code}}" "{ADMIN_URL}" 2>/dev/null)"; then '
        'curl_exit=0; else curl_exit=$?; fi; '
        'printf "curl_exit=%s http_status=%s\\n" "$curl_exit" "${status:-000}"'
    )
    try:
        kubectl(
            "run",
            pod_name,
            f"--namespace={ADMIN_CLIENT_NAMESPACE}",
            f"--image={ADMIN_CLIENT_IMAGE}",
            "--restart=Never",
            "--quiet",
            "--command",
            "--",
            "/bin/sh",
            "-c",
            script,
            timeout=60,
        )
        kubectl(
            "wait",
            f"--namespace={ADMIN_CLIENT_NAMESPACE}",
            f"pod/{pod_name}",
            "--for=jsonpath={.metadata.annotations.ambient\\.istio\\.io/redirection}=enabled",
            "--timeout=120s",
            timeout=130,
        )
        raw_pod = kubectl(
            "get",
            "pod",
            pod_name,
            f"--namespace={ADMIN_CLIENT_NAMESPACE}",
            "--output=json",
        )
        try:
            pod = json.loads(raw_pod)
        except json.JSONDecodeError as error:
            raise VerificationError("Could not inspect the temporary ambient admin probe.") from error
        containers = [
            container.get("name")
            for container in pod.get("spec", {}).get("containers", [])
            + pod.get("spec", {}).get("initContainers", [])
        ]
        if "istio-proxy" in containers:
            raise VerificationError("The admin probe unexpectedly received an Istio sidecar.")
        node = pod.get("spec", {}).get("nodeName")
        if not node:
            raise VerificationError("The ambient admin probe has no assigned Kubernetes node.")
        kubectl(
            "wait",
            f"--namespace={ADMIN_CLIENT_NAMESPACE}",
            f"pod/{pod_name}",
            "--for=jsonpath={.status.phase}=Succeeded",
            "--timeout=120s",
            timeout=130,
        )
    except BaseException as error:
        try:
            delete_admin_probe({"name": pod_name})
        except BaseException as cleanup_error:
            raise VerificationError(
                f"Admin probe failed ({error}); temporary pod cleanup also failed ({cleanup_error})."
            ) from cleanup_error
        raise
    return {"name": pod_name, "node": node}


def delete_admin_probe(client_pod):
    kubectl(
        "delete",
        "pod",
        client_pod["name"],
        f"--namespace={ADMIN_CLIENT_NAMESPACE}",
        "--ignore-not-found=true",
        "--wait=true",
        "--timeout=60s",
        timeout=70,
    )


def verify_runtime():
    check_owner()
    verify_fail_closed()
    check_owner()
    client_pod = run_admin_probe()
    try:
        metrics_by_node = get_ztunnel_metrics_by_node()
        verify_admin_denial(metrics_by_node, client_pod)
    finally:
        delete_admin_probe(client_pod)

    ingress_pods = require_pods(
        "istio-ingress",
        "gateway.networking.k8s.io/gateway-name=gateway",
        "Istio ingress gateway",
    )
    agentgateway_pods = require_pods(
        ADMIN_NAMESPACE,
        "gateway.networking.k8s.io/gateway-name=agentgateway-proxy",
        "Agentgateway proxy",
    )
    diagnostic_pods = require_pods("istio-test", "app=istio-test", "diagnostic workload")

    require_flow_on_relevant_nodes(
        metrics_by_node,
        ingress_pods,
        agentgateway_pods,
        "Istio ingress to Agentgateway",
        source_workload="gateway-istio",
        destination_workload="agentgateway-proxy",
        destination_namespace=ADMIN_NAMESPACE,
    )
    require_flow_on_relevant_nodes(
        metrics_by_node,
        agentgateway_pods,
        diagnostic_pods,
        "Agentgateway to diagnostic workload",
        source_workload="agentgateway-proxy",
        destination_workload="istio-test",
        destination_namespace="istio-test",
    )


def raise_on_termination(signum, _frame):
    raise KeyboardInterrupt(f"Received signal {signum}; restoring owned fixture state.")


def main():
    signal.signal(signal.SIGTERM, raise_on_termination)
    signal.signal(signal.SIGHUP, raise_on_termination)
    try:
        verify_runtime()
    except (VerificationError, KeyboardInterrupt) as error:
        message = str(error) or "Verification interrupted."
        print(f"Runtime gateway verification failed: {message}", file=sys.stderr)
        return 1
    print("All runtime security checks passed; temporary resources and Authentik state were restored.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
