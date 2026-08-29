"""Identity context for ObraSignal API requests."""
from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit

from flask import has_request_context, request
from jwt import (
    DecodeError,
    ExpiredSignatureError,
    ImmatureSignatureError,
    InvalidAudienceError,
    InvalidIssuerError,
    InvalidTokenError,
)

from auth_context_jwt import JwksUnavailableError, production_verifier


_ACCOUNT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
_ALLOWED_AUTH_MODES = {"development", "provider"}
_ALLOWED_ROLES = {"owner", "editor", "viewer"}
_DEFAULT_WEB_ORIGIN = "https://marcostaz.github.io"
_LOGGER = logging.getLogger(__name__)

# A browser Origin never contains a path. GitHub Pages serves the project under
# /Obrasignal/, but the API must receive only the origin (scheme + host).
_configured_cors = (os.getenv("OBRASIGNAL_CORS_ORIGIN") or "").strip()
if not _configured_cors:
    os.environ["OBRASIGNAL_CORS_ORIGIN"] = _DEFAULT_WEB_ORIGIN
elif _configured_cors != "*":
    _parsed_cors = urlsplit(_configured_cors)
    if _parsed_cors.scheme and _parsed_cors.netloc:
        os.environ["OBRASIGNAL_CORS_ORIGIN"] = urlunsplit(
            (_parsed_cors.scheme, _parsed_cors.netloc, "", "", "")
        )


@dataclass(frozen=True)
class RequestIdentity:
    account_id: str
    authenticated: bool
    subject: str | None = None
    claims: dict | None = None
    role: str = "owner"


def _valid_account(account_id: str) -> str:
    account_id = (account_id or "").strip()
    if not _ACCOUNT_RE.fullmatch(account_id):
        raise RuntimeError("Invalid OBRASIGNAL_ACCOUNT_ID")
    return account_id


def _shared_company_membership(subject: str, claims: dict | None) -> tuple[str, str]:
    """Resolve a signed provider membership without trusting client input.

    Supabase/OIDC app metadata is part of the verified JWT payload. A user with no
    ObraSignal organization metadata preserves the historical single-user model:
    subject == account and role == owner. Once either shared-company field appears,
    both fields become mandatory so partial or malformed membership fails closed.
    """
    claims = claims if isinstance(claims, dict) else {}
    metadata = claims.get("app_metadata")
    if metadata is None:
        return _valid_account(subject), "owner"
    if not isinstance(metadata, dict):
        raise InvalidTokenError("invalid app_metadata")

    raw_account = metadata.get("obrasignal_account_id")
    raw_role = metadata.get("obrasignal_role")
    if raw_account is None and raw_role is None:
        return _valid_account(subject), "owner"
    if raw_account is None or raw_role is None:
        raise InvalidTokenError("incomplete ObraSignal membership")

    try:
        account_id = _valid_account(str(raw_account))
    except RuntimeError as exc:
        raise InvalidTokenError("invalid ObraSignal account claim") from exc
    role = str(raw_role).strip().lower()
    if role not in _ALLOWED_ROLES:
        raise InvalidTokenError("invalid ObraSignal role claim")
    return account_id, role


def customer_role_allows(role: str, method: str, *, owner_only: bool = False) -> bool:
    """Return role authorization for a customer-facing HTTP operation.

    Reads are available to all valid company roles. Ordinary writes are available
    to owner/editor. Destructive owner-only boundaries, such as account deletion,
    remain owner-only. Unknown roles always fail closed.
    """
    normalized_role = str(role or "").strip().lower()
    normalized_method = str(method or "").strip().upper()
    if normalized_role not in _ALLOWED_ROLES:
        return False
    if normalized_method in {"GET", "HEAD", "OPTIONS"}:
        return True
    if owner_only:
        return normalized_role == "owner"
    return normalized_role in {"owner", "editor"}


def _invalid_token_reason(error: InvalidTokenError) -> str:
    """Return a bounded diagnostic category without logging token material."""
    if isinstance(error, ExpiredSignatureError):
        return "token_expired"
    if isinstance(error, ImmatureSignatureError):
        return "token_not_yet_valid"
    if isinstance(error, InvalidIssuerError):
        return "issuer_mismatch"
    if isinstance(error, InvalidAudienceError):
        return "audience_mismatch"
    if isinstance(error, DecodeError):
        return "malformed_token"
    message = str(error)
    if message == "unknown JWT key id":
        return "unknown_kid"
    if "algorithm" in message or message == "unsupported JWT header":
        return "unsupported_algorithm"
    return "invalid_token"


def configured_identity() -> RequestIdentity:
    """Resolve identity only from an explicitly selected authentication mode."""
    auth_mode = (os.getenv("OBRASIGNAL_AUTH_MODE") or "").strip().lower()
    if auth_mode not in _ALLOWED_AUTH_MODES:
        raise RuntimeError("Invalid OBRASIGNAL_AUTH_MODE")

    if auth_mode == "development":
        return RequestIdentity(
            account_id=_valid_account(os.getenv("OBRASIGNAL_ACCOUNT_ID") or "default"),
            authenticated=False,
            role="owner",
        )

    if not has_request_context():
        raise RuntimeError("Production authentication provider is not configured")

    authorization = request.headers.get("Authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        _LOGGER.info("auth_failure reason=missing_bearer")
        raise InvalidTokenError("Bearer token required")

    try:
        identity = production_verifier().verify(token.strip())
        account_id, role = _shared_company_membership(identity.subject, identity.claims)
    except JwksUnavailableError:
        _LOGGER.warning("auth_provider_status=degraded reason=jwks_unavailable")
        raise
    except InvalidTokenError as exc:
        _LOGGER.info("auth_failure reason=%s", _invalid_token_reason(exc))
        raise
    except RuntimeError:
        _LOGGER.error("auth_provider_status=misconfigured reason=provider_config")
        raise

    return RequestIdentity(
        account_id=account_id,
        authenticated=True,
        subject=identity.subject,
        claims=identity.claims,
        role=role,
    )
