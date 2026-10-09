#!/usr/bin/env python3
"""Check anonymous gateway behavior without logging credentials or identity."""

import argparse
import http.client
import json
import socket
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, file_pointer, code, message, headers, new_url):
        return None


class LocalConnection(http.client.HTTPSConnection):
    def __init__(self, host, **kwargs):
        super().__init__(host, **kwargs)
        self._create_connection = self.local_socket

    @staticmethod
    def local_socket(address, timeout=15, source_address=None):
        if address[0] not in ("dev.localhost", "agentgateway.localhost", "authentik.localhost"):
            raise RuntimeError("Verification is restricted to local gateway hosts.")
        return socket.create_connection(("127.0.0.1", address[1]), timeout, source_address)


class LocalHTTPSHandler(urllib.request.HTTPSHandler):
    def https_open(self, request):
        return self.do_open(LocalConnection, request, context=self._context)


def response(url, headers=None):
    request = urllib.request.Request(url, headers=headers or {})
    try:
        return OPENER.open(request, timeout=15)
    except urllib.error.HTTPError as error:
        return error


def check_public(url, expected_status=200):
    with response(url) as result:
        if result.code != expected_status or result.headers.get("Location"):
            raise RuntimeError(f"Public endpoint must return {expected_status} without a redirect: {url}")
        return result.read(65536)


def check_diagnostic(url, endpoint):
    try:
        payload = json.loads(check_public(url))
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise RuntimeError(f"Diagnostic endpoint did not return valid JSON: {url}") from error
    if not isinstance(payload, dict):
        raise RuntimeError(f"Diagnostic endpoint returned the wrong JSON shape: {url}")
    if endpoint == "metadata":
        if payload != {"cluster-name": "docker-desktop"}:
            raise RuntimeError(f"Metadata endpoint did not identify the local fixture: {url}")
    else:
        checks = payload.get("checks")
        if payload.get("status") != "healthy" or not isinstance(checks, dict):
            raise RuntimeError(f"Diagnostic workload is not healthy: {url}")
        for name in ("metadata_service", "http_server"):
            check = checks.get(name)
            if not isinstance(check, dict) or check.get("status") != "healthy":
                raise RuntimeError(f"Diagnostic dependency {name} is not healthy: {url}")


def check_protected(url, callback_host, headers=None):
    with response(url, headers) as result:
        location = urllib.parse.urlsplit(result.headers.get("Location", ""))
        callbacks = urllib.parse.parse_qs(location.query).get("redirect_uri", [])
        callback = urllib.parse.urlsplit(callbacks[0]) if len(callbacks) == 1 else None
        if (
            result.code != 302
            or location.scheme != "https"
            or location.netloc != "authentik.localhost"
            or not location.path.startswith("/application/o/authorize/")
            or callback is None
            or callback.scheme != "https"
            or callback.netloc != callback_host
            or callback.path != "/outpost.goauthentik.io/callback"
            or callback.fragment
        ):
            raise RuntimeError(f"Protected endpoint has an invalid authentication redirect: {url}")


OPENER = urllib.request.build_opener(
    urllib.request.ProxyHandler({}),
    LocalHTTPSHandler(context=ssl._create_unverified_context()),
    NoRedirect(),
)


def check_expected_status(url, expected_status, timeout=120, interval=2):
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname not in (
        "dev.localhost",
        "agentgateway.localhost",
        "authentik.localhost",
    ):
        raise RuntimeError("Expected-status checks are restricted to local HTTPS gateway hosts.")
    if not 100 <= expected_status <= 599 or timeout <= 0 or interval <= 0:
        raise RuntimeError("Expected status and polling timeout must be valid positive values.")

    deadline = time.monotonic() + timeout
    last_status = "no response"
    while True:
        try:
            with response(url) as result:
                last_status = str(result.code)
                if result.code == expected_status:
                    return
        except (OSError, http.client.HTTPException):
            last_status = "connection unavailable"

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise RuntimeError(
                f"Expected HTTP {expected_status} from {url} within {timeout}s; "
                f"last observed {last_status}."
            )
        time.sleep(min(interval, remaining))


def main():
    parser = argparse.ArgumentParser(description="Verify local gateway HTTP behavior.")
    parser.add_argument("--expect-status", type=int, help="Poll for this exact HTTP status instead of running the full anonymous suite.")
    parser.add_argument("--timeout", type=int, default=120, help="Maximum wait for --expect-status (default: 120 seconds).")
    parser.add_argument("url", nargs="?", help="Local HTTPS URL used with --expect-status.")
    args = parser.parse_args()

    if args.expect_status is not None:
        if args.url is None:
            parser.error("a URL is required with --expect-status")
        try:
            check_expected_status(args.url, args.expect_status, args.timeout)
            print(f"Observed expected HTTP {args.expect_status} from {args.url}.")
            return
        except (RuntimeError, urllib.error.URLError, TimeoutError) as error:
            print(f"Gateway HTTP verification failed: {error}", file=sys.stderr)
            sys.exit(1)
    if args.url is not None:
        parser.error("URL is only valid with --expect-status")

    for host, prefix in (
        ("dev.localhost", "/istio-test"),
        ("agentgateway.localhost", "/agentgateway-test"),
    ):
        base = f"https://{host}"
        check_diagnostic(base + prefix + "/health", "health")
        check_diagnostic(base + prefix + "/metadata/cluster-name", "metadata")
        check_protected(base + prefix + "/auth", host)
        check_protected(
            base + prefix + "/auth",
            host,
            {
                "X-Authentik-Username": "spoofed",
                "X-Authentik-Email": "spoofed@example.invalid",
                "X-Authentik-Groups": "admins",
            },
        )
        check_public(base + "/outpost.goauthentik.io/ping", expected_status=204)
    check_protected("https://agentgateway.localhost/ui/", "agentgateway.localhost")
    print("Anonymous HTTP checks passed. Real Google sign-in and authenticated checks remain pending.")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, urllib.error.URLError, TimeoutError) as error:
        print(f"Gateway HTTP verification failed: {error}", file=sys.stderr)
        sys.exit(1)
