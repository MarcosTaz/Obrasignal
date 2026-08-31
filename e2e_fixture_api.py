"""Bounded deterministic opportunity fixture contract for authenticated E2E.

The fixture store is deliberately separate from the primary ObraSignal database.
The contract is disabled unless explicitly enabled and configured with a distinct
SQLite path, so test fixtures can never become production opportunity truth.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import re
import sqlite3

from flask import Blueprint, jsonify, request
from jwt import InvalidTokenError

from auth_context import configured_identity
from opportunity_workflow import ensure_workflow_table, get_workflow, set_workflow


bp = Blueprint("e2e_fixture_api", __name__, url_prefix="/api/v1")

_FLAG = "OBRASIGNAL_TEST_FIXTURES_ENABLED"
_DB_ENV = "OBRASIGNAL_TEST_FIXTURE_DB"
_RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
_SOURCE = "OBRASIGNAL_E2E_FIXTURE"


class FixtureConfigurationError(RuntimeError):
    pass


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _primary_db_path() -> Path:
    value = os.getenv("OBRASIGNAL_DB") or str(Path(__file__).with_name("obrasignal.db"))
    return Path(value).expanduser().resolve()


def _fixture_db_path() -> Path:
    if not _truthy(os.getenv(_FLAG)):
        raise FixtureConfigurationError("fixture contract disabled")
    raw = (os.getenv(_DB_ENV) or "").strip()
    if not raw or raw == ":memory:":
        raise FixtureConfigurationError("fixture database is not configured")
    path = Path(raw).expanduser().resolve()
    if path == _primary_db_path():
        raise FixtureConfigurationError("fixture database must be separate from primary data")
    return path


def fixture_store_path() -> Path:
    """Return the validated isolated fixture-store path for external startup orchestration."""
    return _fixture_db_path()


def initialize_fixture_store() -> Path:
    """Initialize the owner schema without owning cross-process serialization."""
    path = fixture_store_path()
    conn = sqlite3.connect(str(path), check_same_thread=False, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=15000")
    try:
        _ensure_schema(conn)
    finally:
        conn.close()
    return path


def _connect() -> sqlite3.Connection:
    path = fixture_store_path()
    conn = sqlite3.connect(str(path), check_same_thread=False, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=15000")
    _ensure_schema(conn)
    return conn


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """CREATE TABLE IF NOT EXISTS e2e_opportunity_fixtures (
               fixture_id TEXT PRIMARY KEY,
               account_id TEXT NOT NULL,
               run_id TEXT NOT NULL,
               source TEXT NOT NULL,
               external_id TEXT NOT NULL,
               created_at TEXT NOT NULL,
               UNIQUE(account_id, run_id),
               UNIQUE(account_id, source, external_id)
           )"""
    )
    conn.execute(
        """CREATE INDEX IF NOT EXISTS idx_e2e_fixture_account_run
           ON e2e_opportunity_fixtures(account_id, run_id)"""
    )
    ensure_workflow_table(conn)
    conn.commit()


def _validate_payload(allowed: set[str]) -> tuple[dict | None, tuple | None]:
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return None, (jsonify({"error": "invalid_fixture_request"}), 400)
    unknown = sorted(set(payload) - allowed)
    if unknown:
        return None, (
            jsonify({"error": "invalid_fixture_request", "unexpected_fields": unknown}),
            400,
        )
    return payload, None


def _validate_run_id(value) -> str | None:
    run_id = str(value or "").strip()
    return run_id if _RUN_ID_RE.fullmatch(run_id) else None


def _fixture_id(account_id: str, run_id: str) -> str:
    digest = hashlib.sha256(f"{account_id}\0{run_id}".encode("utf-8")).hexdigest()[:24]
    return f"e2e_{digest}"


def _fixture_row(conn: sqlite3.Connection, account_id: str, fixture_id: str):
    return conn.execute(
        """SELECT fixture_id, account_id, run_id, source, external_id, created_at
           FROM e2e_opportunity_fixtures
           WHERE account_id=? AND fixture_id=?""",
        (account_id, fixture_id),
    ).fetchone()


def _create_fixture(conn: sqlite3.Connection, account_id: str, run_id: str):
    fixture_id = _fixture_id(account_id, run_id)
    external_id = fixture_id
    created_at = datetime.now(timezone.utc).isoformat()
    with conn:
        cursor = conn.execute(
            """INSERT OR IGNORE INTO e2e_opportunity_fixtures(
                   fixture_id, account_id, run_id, source, external_id, created_at
               ) VALUES (?, ?, ?, ?, ?, ?)""",
            (fixture_id, account_id, run_id, _SOURCE, external_id, created_at),
        )
        row = conn.execute(
            """SELECT fixture_id, account_id, run_id, source, external_id, created_at
               FROM e2e_opportunity_fixtures
               WHERE account_id=? AND run_id=?""",
            (account_id, run_id),
        ).fetchone()
    if row is None or row["fixture_id"] != fixture_id:
        raise RuntimeError("fixture identity conflict")
    return row, cursor.rowcount == 1


def _cleanup_fixture(conn: sqlite3.Connection, account_id: str, run_id: str) -> tuple[str, bool]:
    fixture_id = _fixture_id(account_id, run_id)
    row = _fixture_row(conn, account_id, fixture_id)
    if row is None:
        return fixture_id, False
    with conn:
        conn.execute(
            """DELETE FROM opportunity_workflow
               WHERE account_id=? AND source=? AND external_id=?""",
            (account_id, row["source"], row["external_id"]),
        )
        conn.execute(
            """DELETE FROM e2e_opportunity_fixtures
               WHERE account_id=? AND fixture_id=?""",
            (account_id, fixture_id),
        )
    return fixture_id, True


def _opportunity_payload(row, workflow: dict) -> dict:
    return {
        "id": row["fixture_id"],
        "source": row["source"],
        "external_id": row["external_id"],
        "title": "ObraSignal deterministic E2E fixture",
        "description": "Synthetic test-only opportunity. Not production market data.",
        "buyer": "ObraSignal E2E",
        "country": "PRT",
        "cpv": "45000000",
        "value": None,
        "deadline": "2099-12-31",
        "publication_date": "2000-01-01",
        "url": "https://example.invalid/obrasignal/e2e-fixture",
        "score": 0,
        "first_seen": row["created_at"],
        "last_seen": row["created_at"],
        "market": "TEST",
        "deadline_status": {"state": "open", "label": "Test fixture", "days_remaining": None},
        "is_actionable": True,
        "is_open": True,
        "account_decision": None,
        "account_reason": None,
        "account_score": None,
        "decision_score": None,
        "decision_reason": None,
        "workflow": workflow,
        "test_fixture": True,
        "synthetic": True,
        "fixture_scope": "test-only",
    }


def _identity_or_error():
    try:
        identity = configured_identity()
    except (RuntimeError, InvalidTokenError):
        return None, (jsonify({"error": "authentication_required"}), 401)
    if identity.authenticated is not True:
        return None, (jsonify({"error": "authentication_required"}), 401)
    return identity, None


@bp.before_request
def _fixture_guard():
    if request.method == "OPTIONS":
        return "", 204
    if not _truthy(os.getenv(_FLAG)):
        return jsonify({"error": "not_found"}), 404
    try:
        fixture_store_path()
    except FixtureConfigurationError:
        return jsonify({"error": "fixture_contract_unavailable"}), 503
    identity, error = _identity_or_error()
    if error is not None:
        return error
    request.obrasignal_fixture_identity = identity
    return None


@bp.route("/test-fixtures/opportunity", methods=["POST"])
def create_opportunity_fixture():
    payload, error = _validate_payload({"run_id"})
    if error is not None:
        return error
    run_id = _validate_run_id(payload.get("run_id"))
    if run_id is None:
        return jsonify({"error": "invalid_run_id"}), 400
    identity = request.obrasignal_fixture_identity
    conn = _connect()
    try:
        row, created = _create_fixture(conn, identity.account_id, run_id)
        workflow = get_workflow(conn, identity.account_id, row["source"], row["external_id"])
        body = {
            "ok": True,
            "created": created,
            "run_id": run_id,
            "fixture_id": row["fixture_id"],
            "account_id": identity.account_id,
            "authenticated": identity.authenticated,
            "opportunity": _opportunity_payload(row, workflow),
        }
        return jsonify(body), 201 if created else 200
    finally:
        conn.close()


@bp.route("/test-fixtures/opportunity/cleanup", methods=["POST"])
def cleanup_opportunity_fixture():
    payload, error = _validate_payload({"run_id"})
    if error is not None:
        return error
    run_id = _validate_run_id(payload.get("run_id"))
    if run_id is None:
        return jsonify({"error": "invalid_run_id"}), 400
    identity = request.obrasignal_fixture_identity
    conn = _connect()
    try:
        fixture_id, cleaned = _cleanup_fixture(conn, identity.account_id, run_id)
        return jsonify(
            {
                "ok": True,
                "run_id": run_id,
                "fixture_id": fixture_id,
                "cleaned": cleaned,
                "already_absent": not cleaned,
                "account_id": identity.account_id,
            }
        )
    finally:
        conn.close()


@bp.route("/opportunities/<string:fixture_ref>", methods=["GET"])
def fixture_opportunity_detail(fixture_ref: str):
    if not fixture_ref.startswith("e2e_"):
        return jsonify({"error": "not_found"}), 404
    identity = request.obrasignal_fixture_identity
    conn = _connect()
    try:
        row = _fixture_row(conn, identity.account_id, fixture_ref)
        if row is None:
            return jsonify({"error": "not_found"}), 404
        workflow = get_workflow(conn, identity.account_id, row["source"], row["external_id"])
        return jsonify(_opportunity_payload(row, workflow))
    finally:
        conn.close()


@bp.route("/opportunities/<string:fixture_ref>/workflow", methods=["GET", "POST"])
def fixture_opportunity_workflow(fixture_ref: str):
    if not fixture_ref.startswith("e2e_"):
        return jsonify({"error": "not_found"}), 404
    identity = request.obrasignal_fixture_identity
    conn = _connect()
    try:
        row = _fixture_row(conn, identity.account_id, fixture_ref)
        if row is None:
            return jsonify({"error": "not_found"}), 404
        if request.method == "GET":
            workflow = get_workflow(conn, identity.account_id, row["source"], row["external_id"])
            return jsonify({"workflow": workflow, "account_id": identity.account_id})
        payload = request.get_json(silent=True) or {}
        if not isinstance(payload, dict):
            return jsonify({"error": "invalid_workflow_request"}), 400
        try:
            workflow = set_workflow(
                conn,
                identity.account_id,
                row["source"],
                row["external_id"],
                payload.get("status"),
                payload.get("note"),
            )
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        return jsonify({"ok": True, "workflow": workflow, "account_id": identity.account_id})
    finally:
        conn.close()


def install(app) -> None:
    """Register the fixture blueprint once; the runtime gate remains disabled by default."""
    if bp.name not in app.blueprints:
        app.register_blueprint(bp)
