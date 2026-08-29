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

from account_membership import MembershipAuthorityError, resolve_membership
from auth_context_jwt import JwksUnavailableError, production_verifier


_ACCOUNT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
_ALLOWED_AUTH_MODES = {"development", "provider"}
_ALLOWED_MEMBERSHIP_MODES = {"subject", "database"}
_DEFAULT_WEB_ORIGIN = "https://marcostaz.github.io"
_LOGGER = logging.getLogger(__name__)

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
    role: str | None = None


def _valid_account(account_id: str) -> str:
    account_id = (account_id or "").strip()
    if not _ACCOUNT_RE.fullmatch(account_id):
        raise RuntimeError("Invalid OBRASIGNAL_ACCOUNT_ID")
    return account_id


def _provider_membership(identity) -> tuple[str, str | None]:
    mode = (os.getenv("OBRASIGNAL_ACCOUNT_MEMBERSHIP_MODE") or "subject").strip().lower()
    if mode not in _ALLOWED_MEMBERSHIP_MODES:
        raise RuntimeError("Invalid OBRASIGNAL_ACCOUNT_MEMBERSHIP_MODE")
    if mode == "subject":
        return _valid_account(identity.account_id), None

    database_path = (
        os.getenv("OBRASIGNAL_MEMBERSHIP_DB")
        or os.getenv("OBRASIGNAL_DB")
        or ""
    ).strip()
    membership = resolve_membership(database_path, identity.subject)
    return _valid_account(membership.account_id), membership.role


def _invalid_token_reason(error: InvalidTokenError) -> str:
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
    auth_mode = (os.getenv("OBRASIGNAL_AUTH_MODE") or "development").strip().lower()
    if auth_mode not in _ALLOWED_AUTH_MODES:
        raise RuntimeError("Invalid OBRASIGNAL_AUTH_MODE")

    if auth_mode == "development":
        return RequestIdentity(
            account_id=_valid_account(os.getenv("OBRASIGNAL_ACCOUNT_ID") or "default"),
            authenticated=False,
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
        account_id, role = _provider_membership(identity)
    except JwksUnavailableError:
        _LOGGER.warning("auth_provider_status=degraded reason=jwks_unavailable")
        raise
    except InvalidTokenError as exc:
        _LOGGER.info("auth_failure reason=%s", _invalid_token_reason(exc))
        raise
    except MembershipAuthorityError:
        _LOGGER.info("auth_failure reason=membership_not_authorized")
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
