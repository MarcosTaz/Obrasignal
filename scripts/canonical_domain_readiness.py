"""Fail closed when the customer-facing ObraSignal domain is not truly live.

The browser E2E deliberately has a GitHub Pages fallback so application health
can still be proven while a registrar/DNS provider is blocked.  This probe is
the complementary truth gate: fallback success must never be reported as
canonical-domain readiness.
"""

from __future__ import annotations

import json
import os
import socket
import ssl
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener


CANONICAL_URL = os.environ.get("CANONICAL_URL", "https://obrasignal.com/").rstrip("/") + "/"
TARGET_BUILD = os.environ.get("TARGET_BUILD", "").strip()
TIMEOUT = float(os.environ.get("DOMAIN_PROBE_TIMEOUT", "15"))


class CanonicalRedirectsOnly(HTTPRedirectHandler):
    """Allow only apex <-> www redirects; never silently accept a fallback host."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        source = urlparse(CANONICAL_URL)
        target = urlparse(newurl)
        allowed_hosts = {source.hostname, f"www.{source.hostname}"}
        if target.scheme != "https" or target.hostname not in allowed_hosts:
            raise RuntimeError(
                f"unexpected_redirect:{newurl} (allowed hosts: {sorted(allowed_hosts)})"
            )
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def emit(status: str, **details) -> None:
    print(json.dumps({"status": status, **details}, sort_keys=True))


def fail(status: str, **details) -> int:
    emit(status, **details)
    return 1


def resolve(host: str) -> list[str]:
    infos = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    return sorted({item[4][0] for item in infos})


def main() -> int:
    parsed = urlparse(CANONICAL_URL)
    if parsed.scheme != "https" or not parsed.hostname:
        return fail("invalid_canonical_url", canonical_url=CANONICAL_URL)

    try:
        addresses = resolve(parsed.hostname)
    except socket.gaierror as exc:
        return fail(
            "dns_resolution_failed",
            canonical_url=CANONICAL_URL,
            host=parsed.hostname,
            error=str(exc),
        )
    if not addresses:
        return fail("dns_resolution_empty", host=parsed.hostname)

    marker_url = urljoin(CANONICAL_URL, "release-source.txt")
    opener = build_opener(CanonicalRedirectsOnly())
    request = Request(
        marker_url,
        headers={"User-Agent": "ObraSignal-Canonical-Readiness/1.0", "Cache-Control": "no-cache"},
        method="GET",
    )
    try:
        response = opener.open(request, timeout=TIMEOUT)
        with response:
            final_url = response.geturl()
            status_code = response.getcode()
            body = response.read(512).decode("utf-8", errors="replace").strip()
    except HTTPError as exc:
        return fail(
            "canonical_http_failed",
            canonical_url=CANONICAL_URL,
            marker_url=marker_url,
            dns=addresses,
            http_status=exc.code,
            error=str(exc),
        )
    except (URLError, ssl.SSLError, TimeoutError, OSError, RuntimeError) as exc:
        reason = getattr(exc, "reason", exc)
        text = str(reason)
        status = "canonical_tls_or_network_failed"
        if isinstance(reason, ssl.SSLError) or "CERTIFICATE" in text.upper() or "SSL" in text.upper():
            status = "canonical_tls_failed"
        return fail(
            status,
            canonical_url=CANONICAL_URL,
            marker_url=marker_url,
            dns=addresses,
            error=text,
        )

    if status_code != 200:
        return fail(
            "canonical_http_failed",
            canonical_url=CANONICAL_URL,
            final_url=final_url,
            dns=addresses,
            http_status=status_code,
        )

    final_host = urlparse(final_url).hostname
    allowed_hosts = {parsed.hostname, f"www.{parsed.hostname}"}
    if final_host not in allowed_hosts:
        return fail(
            "canonical_escaped_to_fallback",
            canonical_url=CANONICAL_URL,
            final_url=final_url,
            dns=addresses,
        )

    if TARGET_BUILD and body != TARGET_BUILD:
        return fail(
            "canonical_wrong_build",
            canonical_url=CANONICAL_URL,
            final_url=final_url,
            dns=addresses,
            expected_build=TARGET_BUILD,
            served_build=body,
        )

    emit(
        "canonical_ready",
        canonical_url=CANONICAL_URL,
        final_url=final_url,
        dns=addresses,
        served_build=body,
        expected_build=TARGET_BUILD or None,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
