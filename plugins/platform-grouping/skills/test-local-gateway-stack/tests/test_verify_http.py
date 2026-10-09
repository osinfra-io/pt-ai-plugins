import importlib.util
import json
import unittest
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location(
    "verify_http", Path(__file__).parent.parent / "scripts/verify-http.py"
)
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)


class Response:
    def __init__(self, status, location=None, body=b""):
        self.code = status
        self.headers = {} if location is None else {"Location": location}
        self.body = body

    def read(self, limit):
        return self.body[:limit]

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class HTTPVerificationTests(unittest.TestCase):
    def test_public_requires_exact_status(self):
        for status in (204, 302, 503):
            with self.subTest(status=status), patch.object(verifier, "response", return_value=Response(status)):
                with self.assertRaises(RuntimeError):
                    verifier.check_public("https://dev.localhost/istio-test/health")

    def test_public_rejects_location_even_with_200(self):
        with patch.object(verifier, "response", return_value=Response(200, "https://authentik.localhost/")):
            with self.assertRaises(RuntimeError):
                verifier.check_public("https://dev.localhost/istio-test/health")

    def test_ping_requires_204(self):
        with patch.object(verifier, "response", return_value=Response(204)):
            verifier.check_public("https://dev.localhost/outpost.goauthentik.io/ping", 204)

    def test_protected_requires_correct_callback(self):
        location = (
            "https://authentik.localhost/application/o/authorize/"
            "?redirect_uri=https%3A%2F%2Fdev.localhost%2Foutpost.goauthentik.io%2Fcallback"
        )
        with patch.object(verifier, "response", return_value=Response(302, location)):
            verifier.check_protected("https://dev.localhost/istio-test/auth", "dev.localhost")
            with self.assertRaises(RuntimeError):
                verifier.check_protected("https://agentgateway.localhost/agentgateway-test/auth", "agentgateway.localhost")

    def test_protected_rejects_foreign_auth_host(self):
        location = (
            "https://authentik.localhost.example.invalid/application/o/authorize/"
            "?redirect_uri=https%3A%2F%2Fdev.localhost%2Foutpost.goauthentik.io%2Fcallback"
        )
        with patch.object(verifier, "response", return_value=Response(302, location)):
            with self.assertRaises(RuntimeError):
                verifier.check_protected("https://dev.localhost/istio-test/auth", "dev.localhost")

    def test_provider_callback_query_is_allowed(self):
        location = (
            "https://authentik.localhost/application/o/authorize/"
            "?redirect_uri=https%3A%2F%2Fdev.localhost%2Foutpost.goauthentik.io%2Fcallback"
            "%3FX-authentik-auth-callback%3Dtrue"
        )
        with patch.object(verifier, "response", return_value=Response(302, location)):
            verifier.check_protected("https://dev.localhost/istio-test/auth", "dev.localhost")

    def test_protected_rejects_success_without_signin(self):
        with patch.object(verifier, "response", return_value=Response(200)):
            with self.assertRaises(RuntimeError):
                verifier.check_protected("https://dev.localhost/istio-test/auth", "dev.localhost")

    def test_metadata_identifies_actual_fixture(self):
        for cluster in ("docker-desktop", "wrong-cluster"):
            with self.subTest(cluster=cluster), patch.object(
                verifier, "response", return_value=Response(200, body=json.dumps({"cluster-name": cluster}).encode())
            ):
                if cluster == "docker-desktop":
                    verifier.check_diagnostic("https://dev.localhost/istio-test/metadata/cluster-name", "metadata")
                else:
                    with self.assertRaises(RuntimeError):
                        verifier.check_diagnostic("https://dev.localhost/istio-test/metadata/cluster-name", "metadata")

    def test_health_requires_healthy_dependencies(self):
        body = json.dumps({
            "status": "healthy",
            "checks": {"metadata_service": {"status": "healthy"}, "http_server": {"status": "healthy"}},
        }).encode()
        with patch.object(verifier, "response", return_value=Response(200, body=body)):
            verifier.check_diagnostic("https://dev.localhost/istio-test/health", "health")
        with patch.object(verifier, "response", return_value=Response(200, body=b'{"status":"healthy"}')):
            with self.assertRaises(RuntimeError):
                verifier.check_diagnostic("https://dev.localhost/istio-test/health", "health")

    def test_login_html_cannot_pass_as_diagnostic(self):
        with patch.object(verifier, "response", return_value=Response(200, body=b"<html>Login</html>")):
            with self.assertRaises(RuntimeError):
                verifier.check_diagnostic("https://dev.localhost/istio-test/health", "health")

    def test_expected_status_waits_for_policy_propagation(self):
        responses = [Response(200), Response(302)]
        with (
            patch.object(verifier, "response", side_effect=responses),
            patch.object(verifier.time, "sleep"),
        ):
            verifier.check_expected_status(
                "https://dev.localhost/istio-test/metadata/cluster-name",
                302,
                timeout=10,
                interval=1,
            )

    def test_expected_status_retries_connection_level_errors(self):
        for error in (
            ConnectionResetError("connection reset"),
            verifier.http.client.RemoteDisconnected("connection closed"),
        ):
            with self.subTest(error=type(error).__name__):
                with (
                    patch.object(verifier, "response", side_effect=[error, Response(302)]),
                    patch.object(verifier.time, "sleep"),
                ):
                    verifier.check_expected_status(
                        "https://dev.localhost/istio-test/metadata/cluster-name",
                        302,
                        timeout=10,
                        interval=1,
                    )

    def test_expected_status_rejects_nonlocal_urls(self):
        with self.assertRaisesRegex(RuntimeError, "restricted to local HTTPS gateway hosts"):
            verifier.check_expected_status("https://example.invalid/path", 302)

    def test_expected_status_reports_last_response_on_timeout(self):
        with (
            patch.object(verifier, "response", return_value=Response(200)),
            patch.object(verifier.time, "monotonic", side_effect=[0, 2]),
        ):
            with self.assertRaisesRegex(RuntimeError, "last observed 200"):
                verifier.check_expected_status(
                    "https://dev.localhost/istio-test/metadata/cluster-name",
                    302,
                    timeout=1,
                    interval=1,
                )


if __name__ == "__main__":
    unittest.main()
