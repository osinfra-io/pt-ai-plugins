#!/usr/bin/env python3
"""Check anonymous gateway behavior without logging credentials or identity."""

import http.client
import json
import socket
import ssl
import sys
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


def main():
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
