"""Verified identity context for API requests."""
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
_DEFAULT_WEB_ORIGIN = "https://marcostaz.github.io"
_DEFAULT_TENANT_CLAIM = "sub"
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


def _valid_account(account_id: str) -> str:
    account_id = (account_id or "").strip()
    if not _ACCOUNT_RE.fullmatch(account_id):
        raise RuntimeError("Invalid OBRASIGNAL_ACCOUNT_ID")
    return account_id


def _claim_value(claims: dict, claim_path: str):
    value = claims
    for part in claim_path.split("."):
        if not part or not isinstance(value, dict) or part not in value:
            raise InvalidTokenError("verified tenant claim is missing")
        value = value[part]
    return value


def _verified_tenant_id(claims: dict, subject: str) -> str:
    claim_path = (os.getenv("OBRASIGNAL_JWT_TENANT_CLAIM") or _DEFAULT_TENANT_CLAIM).strip()
    if not claim_path:
        raise RuntimeError("OBRASIGNAL_JWT_TENANT_CLAIM is invalid")
    value = subject if claim_path == "sub" else _claim_value(claims, claim_path)
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise InvalidTokenError("verified tenant claim must be a scalar identifier")
    tenant_id = str(value).strip()
    if not tenant_id:
        raise InvalidTokenError("verified tenant claim is empty")
    return tenant_id


def _mfa_required() -> bool:
    value = (os.getenv("CERTACTUM_REQUIRE_MFA") or "").strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off", ""}:
        return False
    raise RuntimeError("CERTACTUM_REQUIRE_MFA is invalid")


def _enforce_mfa_assurance(claims: dict) -> None:
    """Require a provider-signed AAL2 session when production MFA is enabled.

    Supabase Auth encodes the authenticator assurance level in the signed ``aal``
    JWT claim. We deliberately do not inspect user_metadata or a caller header.
    Missing or non-AAL2 assurance fails closed once CERTACTUM_REQUIRE_MFA is on.
    """
    if not _mfa_required():
        return
    aal = claims.get("aal") if isinstance(claims, dict) else None
    if aal != "aal2":
        raise InvalidTokenError("mfa assurance level is insufficient")


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
    if "tenant claim" in message:
        return "tenant_claim_invalid"
    if "mfa assurance" in message:
        return "mfa_required"
    return "invalid_token"


def configured_identity() -> RequestIdentity:
    auth_mode = (os.getenv("OBRASIGNAL_AUTH_MODE") or "development").strip().lower()
    if auth_mode not in _ALLOWED_AUTH_MODES:
        raise RuntimeError("Invalid OBRASIGNAL_AUTH_MODE")

    if auth_mode == "development":
        deployment = (os.getenv("OBRASIGNAL_ENV") or os.getenv("FLASK_ENV") or "").strip().lower()
        render_hosted = (os.getenv("RENDER") or "").strip().lower() in {"true", "1"}
        if deployment in {"production", "prod"} or render_hosted:
            raise RuntimeError("Development authentication is forbidden on a production deployment")
        return RequestIdentity(
            account_id=_valid_account(os.getenv("OBRASIGNAL_ACCOUNT_ID") or "default"),
            authenticated=False,
        )

    if not has_request_context():
        raise RuntimeError("Production authentication provider is not configured")

    cached = getattr(request, "obrasignal_identity", None)
    if isinstance(cached, RequestIdentity) and cached.authenticated:
        return cached

    authorization = request.headers.get("Authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        _LOGGER.info("auth_failure reason=missing_bearer")
        raise InvalidTokenError("Bearer token required")

    try:
        identity = production_verifier().verify(token.strip())
        claims = identity.claims if isinstance(identity.claims, dict) else {}
        _enforce_mfa_assurance(claims)
        account_id = _valid_account(_verified_tenant_id(claims, identity.subject))
    except JwksUnavailableError:
        _LOGGER.warning("auth_provider_status=degraded reason=jwks_unavailable")
        raise
    except InvalidTokenError as exc:
        _LOGGER.info("auth_failure reason=%s", _invalid_token_reason(exc))
        raise
    except RuntimeError:
        _LOGGER.error("auth_provider_status=misconfigured reason=provider_config")
        raise

    resolved = RequestIdentity(
        account_id=account_id,
        authenticated=True,
        subject=identity.subject,
        claims=identity.claims,
    )
    request.obrasignal_identity = resolved
    return resolved
