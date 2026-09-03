from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


class SharedPlatformError(RuntimeError):
    pass


@dataclass(frozen=True)
class TenantContext:
    tenant_id: str
    actor_id: str
    roles: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.tenant_id.strip() or not self.actor_id.strip():
            raise SharedPlatformError("tenant_id and actor_id are required")
        if len(set(self.roles)) != len(self.roles):
            raise SharedPlatformError("roles must be unique")

    def require_role(self, *allowed: str) -> None:
        if not set(self.roles).intersection(allowed):
            raise SharedPlatformError("actor lacks required tenant-scoped role")


@dataclass(frozen=True)
class AuditEvent:
    event_id: str
    tenant_id: str
    actor_id: str
    event_type: str
    occurred_at: str
    subject_ref: str
    evidence_refs: tuple[str, ...] = ()
    payload_hash: str = ""

    @classmethod
    def create(
        cls,
        *,
        event_id: str,
        context: TenantContext,
        event_type: str,
        subject_ref: str,
        payload: dict[str, Any] | None = None,
        evidence_refs: tuple[str, ...] = (),
        occurred_at: str | None = None,
    ) -> "AuditEvent":
        if not event_id or not event_type or not subject_ref:
            raise SharedPlatformError("audit identity, type and subject are required")
        canonical = json.dumps(payload or {}, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
        return cls(
            event_id=event_id,
            tenant_id=context.tenant_id,
            actor_id=context.actor_id,
            event_type=event_type,
            occurred_at=occurred_at or datetime.now(timezone.utc).isoformat(),
            subject_ref=subject_ref,
            evidence_refs=tuple(sorted(set(evidence_refs))),
            payload_hash=hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        )


@dataclass(frozen=True)
class NotificationEvent:
    event_id: str
    tenant_id: str
    event_type: str
    subject_ref: str
    idempotency_key: str
    payload: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        *,
        event_id: str,
        tenant_id: str,
        event_type: str,
        subject_ref: str,
        payload: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> "NotificationEvent":
        if not event_id or not tenant_id or not event_type or not subject_ref:
            raise SharedPlatformError("notification identity, tenant, type and subject are required")
        key = idempotency_key or hashlib.sha256(
            f"{tenant_id}|{event_type}|{subject_ref}|{event_id}".encode("utf-8")
        ).hexdigest()
        return cls(event_id, tenant_id, event_type, subject_ref, key, dict(payload or {}))


class InMemoryOutbox:
    """Provider-neutral idempotency contract; persistence/provider remains consumer-owned."""

    def __init__(self) -> None:
        self._events: dict[str, NotificationEvent] = {}

    def add(self, event: NotificationEvent) -> bool:
        existing = self._events.get(event.idempotency_key)
        if existing is None:
            self._events[event.idempotency_key] = event
            return True
        if existing != event:
            raise SharedPlatformError("idempotency key collision with different notification payload")
        return False

    def pending(self, tenant_id: str | None = None) -> tuple[NotificationEvent, ...]:
        values = tuple(self._events.values())
        if tenant_id is None:
            return values
        return tuple(event for event in values if event.tenant_id == tenant_id)


def assert_tenant_context(context: TenantContext, *objects: Any) -> None:
    for obj in objects:
        if str(getattr(obj, "tenant_id", "")) != context.tenant_id:
            raise SharedPlatformError("cross-tenant access rejected")
