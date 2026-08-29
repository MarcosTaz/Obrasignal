from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from factory_cloud.assurance_store import SCHEMA_VERSION


@dataclass(frozen=True)
class AssuranceHealth:
    status: str
    integrity: str
    schema_version: int | None
    open_findings: int
    pending_notifications: int
    audit_events: int

    def public_dict(self) -> dict:
        """Minimal readiness surface safe for unauthenticated infrastructure probes."""
        return {
            "status": self.status,
            "integrity": self.integrity,
            "schema_version": self.schema_version,
        }

    def operational_dict(self) -> dict:
        """Aggregate operational metrics for trusted internal/operator surfaces only."""
        return self.public_dict() | {
            "open_findings": self.open_findings,
            "pending_notifications": self.pending_notifications,
            "audit_events": self.audit_events,
        }


def assurance_health(path: str | Path) -> AssuranceHealth:
    """Evaluate local assurance-store health without returning customer identifiers."""
    db = Path(path)
    if not db.is_file():
        return AssuranceHealth("unavailable", "missing", None, 0, 0, 0)
    try:
        conn = sqlite3.connect(db)
        try:
            integrity_row = conn.execute("PRAGMA integrity_check").fetchone()
            integrity = str(integrity_row[0] if integrity_row else "unknown")
            version_row = conn.execute("SELECT value FROM assurance_meta WHERE key='schema_version'").fetchone()
            version = int(version_row[0]) if version_row else None
            open_findings = int(conn.execute(
                "SELECT COUNT(*) FROM findings WHERE state IN ('READY_FOR_REVIEW','APPROVED','ACTIONED')"
            ).fetchone()[0])
            pending_notifications = int(conn.execute(
                "SELECT COUNT(*) FROM notification_outbox WHERE delivered_at IS NULL"
            ).fetchone()[0])
            audit_events = int(conn.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0])
        finally:
            conn.close()
    except (sqlite3.Error, TypeError, ValueError):
        return AssuranceHealth("unavailable", "error", None, 0, 0, 0)

    status = "ready" if integrity == "ok" and version == SCHEMA_VERSION else "unavailable"
    return AssuranceHealth(status, integrity, version, open_findings, pending_notifications, audit_events)
