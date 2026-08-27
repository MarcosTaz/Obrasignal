from __future__ import annotations

import ipaddress
import socket
from urllib.parse import unquote, urljoin, urlsplit, urlunsplit


class UnsafeDestination(ValueError):
    """Raised when a URL would grant broader network authority than intended."""


def safe_local_redirect_target(candidate: str | None, fallback: str) -> str:
    """Return only an application-local absolute path after authentication.

    Encoded and backslash variants are decoded/rejected so an authentication
    success can never become authority to redirect the browser to another origin.
    """
    if not isinstance(candidate, str) or not candidate.strip():
        return fallback
    target = candidate.strip()
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in target):
        return fallback
    for _ in range(4):
        decoded = unquote(target)
        if decoded == target:
            break
        target = decoded
    if "\\" in target or not target.startswith("/") or target.startswith("//"):
        return fallback
    try:
        parts = urlsplit(target)
    except ValueError:
        return fallback
    if parts.scheme or parts.netloc or not parts.path.startswith("/") or parts.path.startswith("//"):
        return fallback
    return target


def _public_addresses(host: str, port: int) -> tuple[str, ...]:
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        try:
            infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        except OSError as exc:
            raise UnsafeDestination("destination host could not be resolved") from exc
        addresses = []
        for info in infos:
            raw = info[4][0]
            try:
                address = ipaddress.ip_address(raw)
            except ValueError as exc:
                raise UnsafeDestination("destination resolution returned an invalid address") from exc
            addresses.append(address)
        if not addresses:
            raise UnsafeDestination("destination host resolved to no addresses")
    else:
        addresses = [literal]

    unique: list[str] = []
    for address in addresses:
        if not address.is_global:
            raise UnsafeDestination("destination resolves to a non-public address")
        text = str(address)
        if text not in unique:
            unique.append(text)
    return tuple(unique)


def validate_public_http_url(url: str, *, resolve_dns: bool = True) -> str:
    """Validate and normalize a public HTTP(S) application URL.

    The policy rejects credentials, localhost/private/link-local/reserved address
    space, non-HTTP schemes, control/backslash ambiguity and query/fragment input.
    Literal IPs are always checked for public routability, even when DNS lookup is
    intentionally skipped. DNS hostnames are resolved before network use.
    """
    if not isinstance(url, str) or not url.strip():
        raise UnsafeDestination("application_url is required")
    raw = url.strip()
    if "\\" in raw or any(ord(ch) < 32 or ord(ch) == 127 for ch in raw):
        raise UnsafeDestination("application_url contains unsafe characters")
    try:
        parts = urlsplit(raw)
    except ValueError as exc:
        raise UnsafeDestination("application_url is malformed") from exc
    scheme = parts.scheme.lower()
    if scheme not in {"http", "https"}:
        raise UnsafeDestination("application_url must use http or https")
    if parts.username is not None or parts.password is not None:
        raise UnsafeDestination("application_url must not contain userinfo")
    if parts.query or parts.fragment:
        raise UnsafeDestination("application_url must not contain query or fragment")
    host = parts.hostname
    if not host:
        raise UnsafeDestination("application_url must include a hostname")
    host = host.rstrip(".").lower()
    try:
        host = host.encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise UnsafeDestination("application_url hostname is invalid") from exc
    if host == "localhost" or host.endswith(".localhost"):
        raise UnsafeDestination("localhost destinations are not authorized")
    try:
        port = parts.port
    except ValueError as exc:
        raise UnsafeDestination("application_url port is invalid") from exc
    if port is not None and not (1 <= port <= 65535):
        raise UnsafeDestination("application_url port is invalid")
    effective_port = port or (443 if scheme == "https" else 80)

    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    if literal is not None:
        if not literal.is_global:
            raise UnsafeDestination("destination resolves to a non-public address")
        display_host = f"[{host}]" if literal.version == 6 else host
    else:
        if resolve_dns:
            _public_addresses(host, effective_port)
        display_host = host

    netloc = display_host + (f":{port}" if port is not None else "")
    path = parts.path or ""
    return urlunsplit((scheme, netloc, path.rstrip("/"), "", ""))


def validated_redirect_target(current_url: str, location: str, *, original_host: str) -> str:
    """Resolve one HTTP redirect and keep health checks on the original host."""
    if not isinstance(location, str) or not location.strip():
        raise UnsafeDestination("redirect response did not provide a location")
    target = validate_public_http_url(urljoin(current_url, location.strip()))
    target_host = (urlsplit(target).hostname or "").rstrip(".").lower()
    if target_host != original_host.rstrip(".").lower():
        raise UnsafeDestination("cross-host health redirects are not authorized")
    return target
