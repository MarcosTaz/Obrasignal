from __future__ import annotations

import hmac
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Optional


ROLES = ("ANALYST", "REVIEWER", "ADMIN")
ROLE_RANK = {role: index for index, role in enumerate(ROLES)}


@dataclass(frozen=True)
class Credential:
    key_id: str
    organization_id: str
    secret: str
    role: str


class CredentialRegistry:
    def __init__(self, credentials: Iterable[Credential]):
        items = tuple(credentials)
        seen_ids = set()
        seen_secrets = set()
        for credential in items:
            if not credential.key_id.strip():
                raise ValueError("credential key_id is required")
            if not credential.organization_id.strip():
                raise ValueError("credential organization_id is required")
            if not credential.secret:
                raise ValueError("credential secret is required")
            if credential.role not in ROLE_RANK:
                raise ValueError(f"unsupported credential role: {credential.role}")
            if credential.key_id in seen_ids:
                raise ValueError("credential key_id must be unique")
            if credential.secret in seen_secrets:
                raise ValueError("credential secret must be unique")
            seen_ids.add(credential.key_id)
            seen_secrets.add(credential.secret)
        self._credentials = items

    @classmethod
    def from_config(cls, config: Any) -> "CredentialRegistry":
        if config is None:
            return cls(())

        # Backward-compatible injected/test shape: {"ORG-A": "secret"}.
        # It receives ANALYST only, never REVIEWER/ADMIN implicitly.
        if isinstance(config, Mapping) and "keys" not in config:
            credentials = []
            for org_id, secret in config.items():
                if isinstance(secret, str) and str(org_id).strip() and secret:
                    credentials.append(Credential(
                        key_id=f"legacy:{str(org_id).strip()}",
                        organization_id=str(org_id).strip(),
                        secret=secret,
                        role="ANALYST",
                    ))
            return cls(credentials)

        if not isinstance(config, Mapping):
            raise ValueError("credential configuration must be an object")
        raw_keys = config.get("keys")
        if not isinstance(raw_keys, list):
            raise ValueError("credential configuration requires a keys array")
        credentials = []
        for item in raw_keys:
            if not isinstance(item, Mapping):
                raise ValueError("credential entries must be objects")
            credentials.append(Credential(
                key_id=str(item.get("key_id") or "").strip(),
                organization_id=str(item.get("organization_id") or "").strip(),
                secret=str(item.get("secret") or ""),
                role=str(item.get("role") or "").strip().upper(),
            ))
        return cls(credentials)

    @property
    def configured(self) -> bool:
        return bool(self._credentials)

    def authenticate(self, supplied_secret: str) -> Optional[Credential]:
        matched: Optional[Credential] = None
        # Compare against every configured secret to avoid an obvious early-exit
        # timing signal about key ordering.
        for credential in self._credentials:
            if hmac.compare_digest(str(supplied_secret or ""), credential.secret):
                matched = credential
        return matched


def role_allows(actual_role: str, required_role: str) -> bool:
    if actual_role not in ROLE_RANK or required_role not in ROLE_RANK:
        return False
    return ROLE_RANK[actual_role] >= ROLE_RANK[required_role]
