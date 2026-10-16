import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location(
    "verify_runtime", Path(__file__).parent.parent / "scripts/verify-runtime.py"
)
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)


class RuntimeVerificationTests(unittest.TestCase):
    def test_mtls_metric_requires_positive_counter_and_identity(self):
        metric = (
            'istio_tcp_sent_bytes_total{source_workload="gateway-istio",'
            'destination_workload="agentgateway-proxy",'
            'destination_service_namespace="agentgateway",'
            'connection_security_policy="mutual_tls"} 32'
        )
        samples = verifier.parse_metrics(metric)
        self.assertTrue(
            verifier.has_mtls_evidence(
                samples,
                "gateway-istio",
                "agentgateway-proxy",
                "agentgateway",
            )
        )

    def test_mtls_metric_rejects_plaintext_and_zero_counters(self):
        for security_policy, counter in (("none", "32"), ("mutual_tls", "0")):
            with self.subTest(security_policy=security_policy, counter=counter):
                metric = (
                    'istio_tcp_sent_bytes_total{source_workload="gateway-istio",'
                    'destination_workload="agentgateway-proxy",'
                    'destination_service_namespace="agentgateway",'
                    f'connection_security_policy="{security_policy}"}} {counter}'
                )
                self.assertFalse(
                    verifier.has_mtls_evidence(
                        verifier.parse_metrics(metric),
                        "gateway-istio",
                        "agentgateway-proxy",
                        "agentgateway",
                    )
                )

    def test_metric_parser_handles_escaped_quotes_and_backslashes(self):
        metric = r'metric_name{label="quote:\"slash:\\end"} 1'
        labels = verifier.parse_metrics(metric)[0].labels
        self.assertEqual(labels, {"label": r"quote:\"slash:\\end"})

    def test_admin_policy_requires_deny_flag(self):
        metric = (
            'istio_tcp_connections_closed_total{source_workload="unauthorized-admin-check",'
            'destination_workload="agentgateway-proxy",'
            'destination_service_namespace="agentgateway",'
            'destination_service_name="agentgateway-proxy-admin",'
            'connection_security_policy="mutual_tls",response_flags="DENY"} 1'
        )
        self.assertTrue(
            verifier.has_mtls_evidence(
                verifier.parse_metrics(metric),
                "unauthorized-admin-check",
                "agentgateway-proxy",
                "agentgateway",
                service_name="agentgateway-proxy-admin",
                denied=True,
            )
        )

    def test_fail_closed_restores_replicas_after_an_unexpected_response(self):
        scales = []

        def fake_kubectl(*args, **_kwargs):
            if args[:2] == ("get", "configmap"):
                return verifier.OWNER_VALUE
            if args[:2] == ("get", "deployment"):
                return "1"
            if args[0] == "scale":
                scales.append(args[-1])
                return ""
            return ""

        with (
            patch.object(verifier, "check_owner"),
            patch.object(verifier, "kubectl", side_effect=fake_kubectl),
            patch.object(verifier, "wait_for_endpoint_presence"),
            patch.object(verifier, "curl_status", return_value=("302", 0)),
            patch.object(verifier, "wait_for_protected_recovery"),
        ):
            with self.assertRaisesRegex(verifier.VerificationError, "observed HTTP 302"):
                verifier.verify_fail_closed()

        self.assertEqual(scales, ["--replicas=0", "--replicas=1"])

    def test_fail_closed_reports_restore_failure_separately(self):
        scales = []

        def fake_kubectl(*args, **_kwargs):
            if args[:2] == ("get", "deployment"):
                return "1"
            if args[0] == "scale":
                scales.append(args[-1])
                if args[-1] == "--replicas=1":
                    raise verifier.VerificationError("simulated restore failure")
                return ""
            return ""

        with (
            patch.object(verifier, "check_owner"),
            patch.object(verifier, "kubectl", side_effect=fake_kubectl),
            patch.object(verifier, "wait_for_endpoint_presence"),
            patch.object(verifier, "curl_status", return_value=("403", 0)),
        ):
            with self.assertRaisesRegex(verifier.VerificationError, "restoration/recovery failed"):
                verifier.verify_fail_closed()

        self.assertEqual(scales, ["--replicas=0", "--replicas=1"])


if __name__ == "__main__":
    unittest.main()
