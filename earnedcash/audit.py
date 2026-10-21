from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json


@dataclass(frozen=True)
class AuditEvent:
    sequence: int
    tenant_id: str
    event_type: str
    entity_id: str
    payload: dict
    previous_hash: str | None
    event_hash: str


def _canonical_event_body(
    *, sequence: int, tenant_id: str, event_type: str, entity_id: str,
    payload: dict, previous_hash: str | None
) -> str:
    return json.dumps(
        {
            "sequence": sequence,
            "tenant_id": tenant_id,
            "event_type": event_type,
            "entity_id": entity_id,
            "payload": payload,
            "previous_hash": previous_hash,
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )


def append_event(
    history: tuple[AuditEvent, ...], *, tenant_id: str, event_type: str,
    entity_id: str, payload: dict
) -> tuple[AuditEvent, ...]:
    if not tenant_id or not event_type or not entity_id:
        raise ValueError("tenant_id, event_type and entity_id are required")
    sequence = len(history) + 1
    previous_hash = history[-1].event_hash if history else None
    body = _canonical_event_body(
        sequence=sequence,
        tenant_id=tenant_id,
        event_type=event_type,
        entity_id=entity_id,
        payload=payload,
        previous_hash=previous_hash,
    )
    event = AuditEvent(
        sequence=sequence,
        tenant_id=tenant_id,
        event_type=event_type,
        entity_id=entity_id,
        payload=dict(payload),
        previous_hash=previous_hash,
        event_hash=sha256(body.encode("utf-8")).hexdigest(),
    )
    return history + (event,)


def verify_history(history: tuple[AuditEvent, ...], *, tenant_id: str) -> bool:
    previous_hash = None
    for expected_sequence, event in enumerate(history, start=1):
        if event.sequence != expected_sequence or event.tenant_id != tenant_id:
            return False
        if event.previous_hash != previous_hash:
            return False
        body = _canonical_event_body(
            sequence=event.sequence,
            tenant_id=event.tenant_id,
            event_type=event.event_type,
            entity_id=event.entity_id,
            payload=event.payload,
            previous_hash=event.previous_hash,
        )
        if sha256(body.encode("utf-8")).hexdigest() != event.event_hash:
            return False
        previous_hash = event.event_hash
    return True
