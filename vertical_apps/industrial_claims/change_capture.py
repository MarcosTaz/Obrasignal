from __future__ import annotations

import re
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from vertical_apps.industrial_claims.proof import sha256_hex


DEFAULT_FACTUAL_WINDOW_HOURS = 72
MIN_FACTUAL_WINDOW_HOURS = 24
MAX_FACTUAL_WINDOW_HOURS = 168
MAX_FACT_TEXT_CHARS = 2_000
MAX_SOURCE_REF_CHARS = 512
_ALLOWED_FACT_TYPES = {
    "REQUESTED_CHANGE",
    "CHANGE_REQUESTED_AT",
    "REQUESTED_BY",
    "AFFECTED_SCOPE",
    "OTHER_FACT",
}
_TENANT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")


class ChangeCaptureError(RuntimeError):
    pass


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_aware(value: object, *, label: str) -> datetime:
    text = str(value or "").strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ChangeCaptureError(f"invalid {label}") from exc
    if parsed.tzinfo is None:
        raise ChangeCaptureError(f"{label} must include timezone")
    return parsed.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    if value.tzinfo is None:
        raise ChangeCaptureError("internal timestamp must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat()


def _required(value: object, *, label: str, max_chars: int) -> str:
    raw = str(value or "")
    if any((ord(ch) < 32 or ord(ch) == 127) and ch not in {"\n", "\r", "\t"} for ch in raw):
        raise ChangeCaptureError(f"invalid {label}")
    text = raw.strip()
    if not text or len(text) > max_chars:
        raise ChangeCaptureError(f"invalid {label}")
    return text


def _tenant(value: object) -> str:
    tenant = _required(value, label="tenant_id", max_chars=64)
    if not _TENANT_RE.fullmatch(tenant):
        raise ChangeCaptureError("invalid tenant_id")
    return tenant


def _window_hours(value: object) -> int:
    try:
        hours = int(value)
    except (TypeError, ValueError) as exc:
        raise ChangeCaptureError("factual window hours must be an integer") from exc
    if hours < MIN_FACTUAL_WINDOW_HOURS or hours > MAX_FACTUAL_WINDOW_HOURS:
        raise ChangeCaptureError(
            f"factual window must be between {MIN_FACTUAL_WINDOW_HOURS} and {MAX_FACTUAL_WINDOW_HOURS} hours"
        )
    return hours


class ChangeCaptureStore:
    """Append-only factual capture around a customer-directed change.

    The operational window is deliberately distinct from any contractual or
    statutory notice deadline. Once the window closes, normal factual input is
    rejected. Existing facts and downloaded snapshots are never rewritten.
    """

    def __init__(self, database: str | Path, *, clock: Callable[[], datetime] = _utc_now) -> None:
        self.path = Path(database)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.clock = clock
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS causledger_change_capture_windows(
                    tenant_id TEXT NOT NULL,
                    finding_id TEXT NOT NULL,
                    sheet_id TEXT NOT NULL UNIQUE,
                    event_ref TEXT NOT NULL,
                    recorded_at TEXT NOT NULL,
                    factual_window_closes_at TEXT NOT NULL,
                    factual_window_hours INTEGER NOT NULL,
                    PRIMARY KEY(tenant_id,finding_id)
                );
                CREATE TABLE IF NOT EXISTS causledger_change_facts(
                    fact_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    finding_id TEXT NOT NULL,
                    fact_type TEXT NOT NULL,
                    fact_text TEXT NOT NULL,
                    source_ref TEXT,
                    actor_id TEXT NOT NULL,
                    recorded_at TEXT NOT NULL,
                    previous_fact_hash TEXT,
                    fact_hash TEXT NOT NULL UNIQUE
                );
                CREATE INDEX IF NOT EXISTS idx_causledger_change_facts_case
                    ON causledger_change_facts(tenant_id,finding_id,recorded_at,fact_id);
                CREATE TABLE IF NOT EXISTS causledger_change_sheet_downloads(
                    download_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    finding_id TEXT NOT NULL,
                    actor_id TEXT NOT NULL,
                    downloaded_at TEXT NOT NULL,
                    sheet_sha256 TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_causledger_change_sheet_downloads_case
                    ON causledger_change_sheet_downloads(tenant_id,finding_id,downloaded_at,download_id);
                CREATE TRIGGER IF NOT EXISTS causledger_change_windows_no_update
                    BEFORE UPDATE ON causledger_change_capture_windows BEGIN SELECT RAISE(ABORT,'change capture windows are append-only'); END;
                CREATE TRIGGER IF NOT EXISTS causledger_change_windows_no_delete
                    BEFORE DELETE ON causledger_change_capture_windows BEGIN SELECT RAISE(ABORT,'change capture windows are append-only'); END;
                CREATE TRIGGER IF NOT EXISTS causledger_change_facts_no_update
                    BEFORE UPDATE ON causledger_change_facts BEGIN SELECT RAISE(ABORT,'change facts are append-only'); END;
                CREATE TRIGGER IF NOT EXISTS causledger_change_facts_no_delete
                    BEFORE DELETE ON causledger_change_facts BEGIN SELECT RAISE(ABORT,'change facts are append-only'); END;
                CREATE TRIGGER IF NOT EXISTS causledger_change_downloads_no_update
                    BEFORE UPDATE ON causledger_change_sheet_downloads BEGIN SELECT RAISE(ABORT,'change sheet downloads are append-only'); END;
                CREATE TRIGGER IF NOT EXISTS causledger_change_downloads_no_delete
                    BEFORE DELETE ON causledger_change_sheet_downloads BEGIN SELECT RAISE(ABORT,'change sheet downloads are append-only'); END;
                """
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _source_case(self, conn: sqlite3.Connection, *, tenant_id: str, finding_id: str) -> tuple[str, datetime]:
        case = conn.execute(
            "SELECT event_ref FROM industrial_claim_cases WHERE tenant_id=? AND finding_id=?",
            (tenant_id, finding_id),
        ).fetchone()
        if case is None:
            raise ChangeCaptureError("tenant-scoped industrial case not found")
        audit = conn.execute(
            """SELECT occurred_at FROM audit_events
               WHERE tenant_id=? AND subject_ref=? AND event_type='industrial_finding_created'
               ORDER BY occurred_at,event_id LIMIT 1""",
            (tenant_id, finding_id),
        ).fetchone()
        if audit is None:
            raise ChangeCaptureError("finding creation timestamp not found")
        return _required(case["event_ref"], label="event_ref", max_chars=512), _parse_aware(
            audit["occurred_at"], label="finding creation timestamp"
        )

    def ensure_window(
        self,
        *,
        tenant_id: str,
        finding_id: str,
        factual_window_hours: int = DEFAULT_FACTUAL_WINDOW_HOURS,
    ) -> dict[str, Any]:
        tenant = _tenant(tenant_id)
        finding = _required(finding_id, label="finding_id", max_chars=2_048)
        hours = _window_hours(factual_window_hours)
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT * FROM causledger_change_capture_windows WHERE tenant_id=? AND finding_id=?",
                (tenant, finding),
            ).fetchone()
            if existing is None:
                event_ref, recorded_at = self._source_case(conn, tenant_id=tenant, finding_id=finding)
                closes_at = recorded_at + timedelta(hours=hours)
                deterministic = sha256_hex(
                    f"CAUSLEDGER_CHANGE_SHEET\n{tenant}\n{finding}\n{event_ref}\n{_iso(recorded_at)}".encode("utf-8")
                )
                sheet_id = f"chg_{deterministic[:24]}"
                conn.execute(
                    """INSERT INTO causledger_change_capture_windows(
                        tenant_id,finding_id,sheet_id,event_ref,recorded_at,
                        factual_window_closes_at,factual_window_hours
                    ) VALUES(?,?,?,?,?,?,?)""",
                    (tenant, finding, sheet_id, event_ref, _iso(recorded_at), _iso(closes_at), hours),
                )
                existing = conn.execute(
                    "SELECT * FROM causledger_change_capture_windows WHERE tenant_id=? AND finding_id=?",
                    (tenant, finding),
                ).fetchone()
            elif int(existing["factual_window_hours"]) != hours:
                raise ChangeCaptureError("existing factual capture window cannot be silently changed")
        if existing is None:
            raise ChangeCaptureError("change capture window could not be established")
        return dict(existing)

    def _facts(self, conn: sqlite3.Connection, *, tenant_id: str, finding_id: str) -> list[sqlite3.Row]:
        return list(
            conn.execute(
                """SELECT * FROM causledger_change_facts
                   WHERE tenant_id=? AND finding_id=? ORDER BY recorded_at,fact_id""",
                (tenant_id, finding_id),
            ).fetchall()
        )

    @staticmethod
    def _verify_fact_chain(rows: list[sqlite3.Row]) -> tuple[bool, str | None, list[str]]:
        previous: str | None = None
        errors: list[str] = []
        for index, row in enumerate(rows):
            body = {
                "fact_id": row["fact_id"],
                "tenant_id": row["tenant_id"],
                "finding_id": row["finding_id"],
                "fact_type": row["fact_type"],
                "fact_text": row["fact_text"],
                "source_ref": row["source_ref"],
                "actor_id": row["actor_id"],
                "recorded_at": row["recorded_at"],
                "previous_fact_hash": row["previous_fact_hash"],
            }
            if row["previous_fact_hash"] != previous:
                errors.append(f"FACT_{index}_PREVIOUS_HASH_MISMATCH")
            expected = sha256_hex(body)
            if str(row["fact_hash"]) != expected:
                errors.append(f"FACT_{index}_HASH_MISMATCH")
            previous = str(row["fact_hash"])
        return not errors, previous, errors

    def add_fact(
        self,
        *,
        tenant_id: str,
        finding_id: str,
        actor_id: str,
        fact_type: str,
        fact_text: str,
        source_ref: str | None = None,
    ) -> dict[str, Any]:
        tenant = _tenant(tenant_id)
        finding = _required(finding_id, label="finding_id", max_chars=2_048)
        actor = _required(actor_id, label="actor_id", max_chars=256)
        kind = _required(fact_type, label="fact_type", max_chars=64).upper()
        if kind not in _ALLOWED_FACT_TYPES:
            raise ChangeCaptureError("unsupported factual change field")
        text = _required(fact_text, label="fact_text", max_chars=MAX_FACT_TEXT_CHARS)
        if kind == "CHANGE_REQUESTED_AT":
            text = _iso(_parse_aware(text, label="declared change requested timestamp"))
        source = None if source_ref is None else _required(source_ref, label="source_ref", max_chars=MAX_SOURCE_REF_CHARS)
        window = self.ensure_window(tenant_id=tenant, finding_id=finding)
        closes_at = _parse_aware(window["factual_window_closes_at"], label="factual window close")
        now = self.clock().astimezone(timezone.utc)
        if now > closes_at:
            raise ChangeCaptureError("factual capture window is closed; use a separately recorded late supplement")
        fact_id = f"fact_{secrets.token_urlsafe(18)}"
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            rows = self._facts(conn, tenant_id=tenant, finding_id=finding)
            valid, previous, errors = self._verify_fact_chain(rows)
            if not valid:
                raise ChangeCaptureError(f"change fact chain integrity failure: {errors}")
            recorded_at = _iso(now)
            body = {
                "fact_id": fact_id,
                "tenant_id": tenant,
                "finding_id": finding,
                "fact_type": kind,
                "fact_text": text,
                "source_ref": source,
                "actor_id": actor,
                "recorded_at": recorded_at,
                "previous_fact_hash": previous,
            }
            digest = sha256_hex(body)
            conn.execute(
                """INSERT INTO causledger_change_facts(
                    fact_id,tenant_id,finding_id,fact_type,fact_text,source_ref,
                    actor_id,recorded_at,previous_fact_hash,fact_hash
                ) VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (fact_id, tenant, finding, kind, text, source, actor, recorded_at, previous, digest),
            )
            conn.commit()
        return {**body, "fact_hash": digest}

    def status(self, *, tenant_id: str, finding_id: str) -> dict[str, Any]:
        tenant = _tenant(tenant_id)
        finding = _required(finding_id, label="finding_id", max_chars=2_048)
        window = self.ensure_window(tenant_id=tenant, finding_id=finding)
        now = self.clock().astimezone(timezone.utc)
        closes_at = _parse_aware(window["factual_window_closes_at"], label="factual window close")
        window_open = now <= closes_at
        with self._connect() as conn:
            facts = self._facts(conn, tenant_id=tenant, finding_id=finding)
            valid, chain_head, errors = self._verify_fact_chain(facts)
            if not valid:
                raise ChangeCaptureError(f"change fact chain integrity failure: {errors}")
            download_count = int(
                conn.execute(
                    "SELECT COUNT(*) AS n FROM causledger_change_sheet_downloads WHERE tenant_id=? AND finding_id=?",
                    (tenant, finding),
                ).fetchone()["n"]
            )
        requested_change_entries = [row for row in facts if row["fact_type"] == "REQUESTED_CHANGE"]
        requested_at_entries = [row for row in facts if row["fact_type"] == "CHANGE_REQUESTED_AT"]
        requested_change = (
            str(requested_change_entries[-1]["fact_text"])
            if requested_change_entries
            else str(window["event_ref"])
        )
        requested_change_source = "DECLARED_FACT" if requested_change_entries else "EVENT_REFERENCE_FALLBACK"
        declared_requested_at = str(requested_at_entries[-1]["fact_text"]) if requested_at_entries else None
        remaining = max(0, int((closes_at - now).total_seconds())) if window_open else 0
        return {
            "sheet_id": window["sheet_id"],
            "finding_id": finding,
            "event_ref": window["event_ref"],
            "requested_change": requested_change,
            "requested_change_source": requested_change_source,
            "declared_change_requested_at": declared_requested_at,
            "declared_change_requested_at_is_externally_verified": False,
            "recorded_at": window["recorded_at"],
            "factual_window_closes_at": window["factual_window_closes_at"],
            "factual_window_hours": int(window["factual_window_hours"]),
            "window_state": "OPEN" if window_open else "CLOSED",
            "fact_entry_allowed": window_open,
            "seconds_remaining": remaining,
            "download_count": download_count,
            "fact_count": len(facts),
            "fact_chain_head_sha256": chain_head,
            "download_prompt": {
                "active": window_open,
                "message": (
                    "Descreva o pedido em uma frase e descarregue a folha de alteração para o registo do projeto."
                    if not requested_change_entries
                    else "Descarregue a folha de alteração e guarde-a com o registo do projeto."
                ),
                "download_path": f"/findings/{finding}/change-sheet",
                "stops_when_factual_window_closes": True,
            },
            "truth_boundary": {
                "operational_capture_window_is_not_contractual_notice_deadline": True,
                "declared_request_time_is_not_certified_external_time": True,
                "fact_capture_does_not_establish_recoverability": True,
            },
        }

    def render_sheet(self, *, tenant_id: str, finding_id: str) -> tuple[str, str]:
        tenant = _tenant(tenant_id)
        finding = _required(finding_id, label="finding_id", max_chars=2_048)
        status = self.status(tenant_id=tenant, finding_id=finding)
        with self._connect() as conn:
            rows = self._facts(conn, tenant_id=tenant, finding_id=finding)
        factual_lines = []
        for row in rows:
            if row["fact_type"] in {"REQUESTED_CHANGE", "CHANGE_REQUESTED_AT"}:
                continue
            source = f" | source: {row['source_ref']}" if row["source_ref"] else ""
            factual_lines.append(f"- {row['fact_type']}: {row['fact_text']}{source}")
        if not factual_lines:
            factual_lines.append("- No additional factual entries recorded.")
        lines = [
            "VINDORUM — CHANGE CAPTURE SHEET",
            "",
            f"Sheet ID: {status['sheet_id']}",
            f"Change reference: {status['event_ref']}",
            f"Requested change: {status['requested_change']}",
            f"Declared request date/time: {status['declared_change_requested_at'] or 'NOT DECLARED'}",
            f"VINDORUM first recorded at: {status['recorded_at']}",
            f"Factual input window closes at: {status['factual_window_closes_at']}",
            f"Factual window status at download: {status['window_state']}",
            "",
            "FACTUAL NOTES",
            *factual_lines,
            "",
            "TRUTH BOUNDARY",
            "This is a contemporaneous factual capture aid. It is not a contractual notice deadline,",
            "does not prove customer responsibility, and does not establish legal recoverability.",
            "The declared request date/time remains a declared fact unless supported by external evidence.",
        ]
        body = "\n".join(lines).rstrip() + "\n"
        digest = sha256_hex(body.encode("utf-8"))
        return body + f"\nSnapshot SHA-256: {digest}\n", digest

    def record_download(
        self,
        *,
        tenant_id: str,
        finding_id: str,
        actor_id: str,
        sheet_sha256: str,
    ) -> dict[str, str]:
        tenant = _tenant(tenant_id)
        finding = _required(finding_id, label="finding_id", max_chars=2_048)
        actor = _required(actor_id, label="actor_id", max_chars=256)
        digest = str(sheet_sha256 or "").strip().lower()
        if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
            raise ChangeCaptureError("invalid change sheet digest")
        self.ensure_window(tenant_id=tenant, finding_id=finding)
        download_id = f"download_{secrets.token_urlsafe(18)}"
        downloaded_at = _iso(self.clock().astimezone(timezone.utc))
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO causledger_change_sheet_downloads(
                    download_id,tenant_id,finding_id,actor_id,downloaded_at,sheet_sha256
                ) VALUES(?,?,?,?,?,?)""",
                (download_id, tenant, finding, actor, downloaded_at, digest),
            )
        return {
            "download_id": download_id,
            "downloaded_at": downloaded_at,
            "sheet_sha256": digest,
        }
