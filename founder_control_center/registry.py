from __future__ import annotations

import json
import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, TypeVar

from .models import ApplicationState, CompanyManifest, Evidence, FactoryState, Metric, RepositoryState, Risk, TruthState
from .security import normalize_source_label, validate_public_http_url
from .seed import build_seed_companies

DB_PATH = os.getenv("FCC_DB", str(Path(__file__).with_name("founder_control_center.db")))
T = TypeVar("T")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=10000")
    return conn


def init_db() -> None:
    with connect() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS companies(id TEXT PRIMARY KEY,payload TEXT NOT NULL,updated_at TEXT NOT NULL)")
        conn.execute("CREATE TABLE IF NOT EXISTS audit_log(id INTEGER PRIMARY KEY AUTOINCREMENT,created_at TEXT NOT NULL,company_id TEXT,actor TEXT NOT NULL,action TEXT NOT NULL,level TEXT NOT NULL,source_data TEXT,result TEXT NOT NULL,failure_state TEXT)")
        conn.execute("CREATE TABLE IF NOT EXISTS company_snapshots(id INTEGER PRIMARY KEY AUTOINCREMENT,company_id TEXT NOT NULL,captured_at TEXT NOT NULL,payload TEXT NOT NULL)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_company_snapshots_company_id ON company_snapshots(company_id,id DESC)")
        conn.commit()
    bootstrap_if_empty()


def _evidence(value):
    return Evidence(**value) if value else None


def _freshness_guard(state: TruthState, evidence: Evidence | None) -> TruthState:
    """A previously good/bad operational state is not current truth without fresh evidence."""
    if state == TruthState.UNKNOWN:
        return state
    if evidence is None:
        return TruthState.UNKNOWN
    freshness = evidence.freshness_state()
    if freshness != TruthState.GREEN:
        return freshness
    return state


def _metric(value):
    if not value:
        return Metric("unknown", "Unknown")
    value = dict(value)
    value["state"] = TruthState(value.get("state", "UNKNOWN"))
    value["evidence"] = _evidence(value.get("evidence"))
    metric = Metric(**value)
    metric.state = _freshness_guard(metric.state, metric.evidence)
    return metric


def _from_payload(payload: dict) -> CompanyManifest:
    repo = dict(payload.get("repository") or {})
    repo["ci"] = TruthState(repo.get("ci", "UNKNOWN"))
    repo["evidence"] = _evidence(repo.get("evidence"))
    repo["ci"] = _freshness_guard(repo["ci"], repo["evidence"])

    app = dict(payload.get("application") or {})
    app["deployment"] = TruthState(app.get("deployment", "UNKNOWN"))
    app["health"] = TruthState(app.get("health", "UNKNOWN"))
    for key in ("evidence", "deployment_evidence", "health_evidence"):
        app[key] = _evidence(app.get(key))
    app["deployment"] = _freshness_guard(app["deployment"], app.get("deployment_evidence"))
    app["health"] = _freshness_guard(app["health"], app.get("health_evidence"))

    risks = []
    for item in payload.get("risks", []):
        item = dict(item)
        item["evidence"] = _evidence(item.get("evidence"))
        risks.append(Risk(**item))

    factories = []
    for item in payload.get("factories", []):
        item = dict(item)
        item["evidence"] = _evidence(item.get("evidence"))
        item["freshness"] = item["evidence"].freshness_state() if item["evidence"] else TruthState.UNKNOWN
        factories.append(FactoryState(**item))

    return CompanyManifest(
        id=payload["id"], name=payload["name"], mission=payload["mission"], kind=payload.get("kind", "company"),
        status=payload.get("status", "UNKNOWN"), stage=payload.get("stage", "UNKNOWN"), active=payload.get("active", "UNKNOWN"),
        next=payload.get("next", "UNKNOWN"), wait=payload.get("wait", "NONE"), business_model=payload.get("business_model", "UNKNOWN"),
        icp=payload.get("icp", "UNKNOWN"), pricing=payload.get("pricing", "UNKNOWN"), revenue=_metric(payload.get("revenue")),
        pipeline=_metric(payload.get("pipeline")), customers=_metric(payload.get("customers")), metrics=[_metric(x) for x in payload.get("metrics", [])],
        risks=risks, opportunities=list(payload.get("opportunities", [])), factories=factories, repository=RepositoryState(**repo),
        application=ApplicationState(**app), priorities=list(payload.get("priorities", [])), last_update=payload.get("last_update"),
        data_freshness=TruthState(payload.get("data_freshness", "UNKNOWN")), synthetic=bool(payload.get("synthetic", False)),
        source_note=payload.get("source_note", "No connected source"),
    )


def _payload_json(company: CompanyManifest) -> str:
    return json.dumps(company.to_dict(), ensure_ascii=False)


def _write_snapshot(conn: sqlite3.Connection, company: CompanyManifest, captured_at: str) -> None:
    conn.execute(
        "INSERT INTO company_snapshots(company_id,captured_at,payload) VALUES(?,?,?)",
        (company.id, captured_at, _payload_json(company)),
    )


def list_companies() -> list[CompanyManifest]:
    with connect() as conn:
        rows = conn.execute("SELECT payload FROM companies ORDER BY id").fetchall()
    return [_from_payload(json.loads(row["payload"])) for row in rows]


def get_company(company_id: str) -> CompanyManifest | None:
    with connect() as conn:
        row = conn.execute("SELECT payload FROM companies WHERE id=?", (company_id,)).fetchone()
    return _from_payload(json.loads(row["payload"])) if row else None


def _snapshot_summary(row: sqlite3.Row) -> dict:
    payload = json.loads(row["payload"])
    repository = payload.get("repository") or {}
    application = payload.get("application") or {}
    factories = payload.get("factories") or []
    live_factory_freshness = [
        item.get("freshness", "UNKNOWN")
        for item in factories
        if (item.get("evidence") or {}).get("kind") == "factory_feed"
    ]
    return {
        "captured_at": row["captured_at"],
        "status": payload.get("status", "UNKNOWN"),
        "stage": payload.get("stage", "UNKNOWN"),
        "active": payload.get("active", "UNKNOWN"),
        "next": payload.get("next", "UNKNOWN"),
        "wait": payload.get("wait", "NONE"),
        "revenue": payload.get("revenue") or {},
        "pipeline": payload.get("pipeline") or {},
        "customers": payload.get("customers") or {},
        "repository": {"commit": repository.get("commit"), "ci": repository.get("ci", "UNKNOWN")},
        "application": {"deployment": application.get("deployment", "UNKNOWN"), "health": application.get("health", "UNKNOWN")},
        "factory_feed_freshness": live_factory_freshness,
    }


def list_company_history(company_id: str, limit: int = 50) -> list[dict]:
    limit = max(1, min(int(limit), 200))
    with connect() as conn:
        rows = conn.execute(
            "SELECT captured_at,payload FROM company_snapshots WHERE company_id=? ORDER BY id DESC LIMIT ?",
            (company_id, limit),
        ).fetchall()
    return [_snapshot_summary(row) for row in rows]


def save_company(company: CompanyManifest) -> None:
    stamp = now_iso()
    company.last_update = stamp
    payload = _payload_json(company)
    with connect() as conn:
        conn.execute("INSERT INTO companies(id,payload,updated_at) VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload,updated_at=excluded.updated_at", (company.id, payload, stamp))
        _write_snapshot(conn, company, stamp)
        conn.commit()


def create_company(company: CompanyManifest) -> None:
    """Insert a new company identity atomically; never overwrite an existing company."""
    stamp = now_iso()
    company.last_update = stamp
    payload = _payload_json(company)
    try:
        with connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("INSERT INTO companies(id,payload,updated_at) VALUES(?,?,?)", (company.id, payload, stamp))
            _write_snapshot(conn, company, stamp)
    except sqlite3.IntegrityError as exc:
        raise ValueError("company_id already exists") from exc


def mutate_company(company_id: str, mutator: Callable[[CompanyManifest], T]) -> tuple[CompanyManifest, T]:
    """Atomically read-modify-write one company row to prevent concurrent feed lost updates."""
    with connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT payload FROM companies WHERE id=?", (company_id,)).fetchone()
        if not row:
            raise ValueError("unknown company_id")
        company = _from_payload(json.loads(row["payload"]))
        result = mutator(company)
        stamp = now_iso()
        company.last_update = stamp
        conn.execute("UPDATE companies SET payload=?, updated_at=? WHERE id=?", (_payload_json(company), stamp, company_id))
        _write_snapshot(conn, company, stamp)
    return company, result


def register_company_stub(*, company_id: str, name: str, mission: str, kind: str = "company", repository_full_name: str | None = None, application_url: str | None = None) -> CompanyManifest:
    """Register a future company without inventing or silently truncating founder-provided identity truth."""
    if not all(isinstance(value, str) for value in (company_id, name, mission, kind)):
        raise ValueError("company_id, name, mission and kind must be strings")
    company_id = company_id.strip().lower()
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,62}[a-z0-9]", company_id):
        raise ValueError("company_id must be a 3-64 character lowercase slug")
    name = name.strip()
    mission = mission.strip()
    kind = kind.strip() or "company"
    if not name or not mission:
        raise ValueError("name and mission are required")
    if len(name) > 120:
        raise ValueError("name must be at most 120 characters")
    if len(mission) > 1000:
        raise ValueError("mission must be at most 1000 characters")
    if len(kind) > 80:
        raise ValueError("kind must be at most 80 characters")
    normalized_application_url = validate_public_http_url(application_url) if application_url else None
    evidence = Evidence(source="founder_manual_registry", observed_at=now_iso(), freshness_seconds=None, kind="manual_registry", detail="Identity fields are founder-provided. Operational status remains UNKNOWN until canonical adapters provide evidence.")
    company = CompanyManifest(
        id=company_id, name=name, mission=mission, kind=kind,
        status="UNKNOWN", stage="UNKNOWN", active="Connect canonical truth sources", next="Establish ACTIVE / NEXT / WAIT from evidence", wait="NONE",
        repository=RepositoryState(full_name=repository_full_name.strip() if repository_full_name else None, evidence=evidence),
        application=ApplicationState(name=name, url=normalized_application_url, evidence=evidence),
        data_freshness=TruthState.UNKNOWN, synthetic=False,
        source_note="Registered manually; business, application and repository health remain UNKNOWN until source adapters prove them.",
    )
    create_company(company)
    append_audit(actor="founder", action="register_company", level="GREEN", company_id=company_id, result="registered_unknown_truth", source_data={"repository": repository_full_name, "application_url_configured": bool(normalized_application_url)})
    return company


def ingest_factory_state(*, company_id: str, factory_name: str, active: str, next_value: str, wait: str, source: str, observed_at: str | None = None, freshness_seconds: int = 3600, material_delta: str | None = None) -> CompanyManifest:
    """Ingest one Factory's own state without truncating or fabricating source truth."""
    if not isinstance(company_id, str) or not company_id.strip() or len(company_id.strip()) > 120:
        raise ValueError("company_id must be a non-empty string of at most 120 characters")
    company_id = company_id.strip()

    raw_fields = {
        "factory_name": (factory_name, 160),
        "active": (active, 1000),
        "next": (next_value, 1000),
        "wait": (wait, 1000),
    }
    normalized_fields: dict[str, str] = {}
    for field, (value, limit) in raw_fields.items():
        if not isinstance(value, str) or not value.strip():
            raise ValueError("factory_name, active, next and wait are required")
        normalized = value.strip()
        if len(normalized) > limit:
            raise ValueError(f"{field} must be at most {limit} characters")
        normalized_fields[field] = normalized

    if material_delta is not None:
        if not isinstance(material_delta, str):
            raise ValueError("material_delta must be a string or null")
        material_delta = material_delta.strip()
        if len(material_delta) > 2000:
            raise ValueError("material_delta must be at most 2000 characters")

    source_label = normalize_source_label(source)
    factory_name = normalized_fields["factory_name"]
    active = normalized_fields["active"]
    next_value = normalized_fields["next"]
    wait = normalized_fields["wait"]

    if observed_at is None:
        observed_at = now_iso()
    elif not isinstance(observed_at, str) or not observed_at.strip():
        raise ValueError("observed_at must be ISO-8601")
    else:
        observed_at = observed_at.strip()
    try:
        parsed = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        incoming_observed = parsed.astimezone(timezone.utc)
        observed_at = incoming_observed.isoformat()
    except (AttributeError, ValueError) as exc:
        raise ValueError("observed_at must be ISO-8601") from exc
    if (incoming_observed - datetime.now(timezone.utc)).total_seconds() > 300:
        raise ValueError("future-dated Factory state evidence rejected")
    if isinstance(freshness_seconds, bool) or not isinstance(freshness_seconds, int):
        raise ValueError("freshness_seconds must be an integer")
    freshness_seconds = max(60, min(freshness_seconds, 7 * 24 * 3600))

    evidence = Evidence(source=source_label, observed_at=observed_at, freshness_seconds=freshness_seconds, kind="factory_feed", detail="Factory-owned ACTIVE/NEXT/WAIT feed; does not override global company truth.")
    incoming_fingerprint = (active, next_value, wait, material_delta, source_label, freshness_seconds)

    def apply(company: CompanyManifest) -> FactoryState:
        existing = next((item for item in company.factories if item.name == factory_name), None)
        if existing and existing.evidence and existing.evidence.kind == "factory_feed" and existing.evidence.observed_at:
            try:
                current_observed = datetime.fromisoformat(existing.evidence.observed_at.replace("Z", "+00:00"))
                if current_observed.tzinfo is None:
                    current_observed = current_observed.replace(tzinfo=timezone.utc)
                current_observed = current_observed.astimezone(timezone.utc)
            except (AttributeError, ValueError) as exc:
                raise ValueError("existing Factory state evidence has invalid observed_at") from exc
            if incoming_observed < current_observed:
                raise ValueError("out-of-order Factory state evidence rejected")
            if incoming_observed == current_observed:
                existing_fingerprint = (
                    existing.active,
                    existing.next,
                    existing.wait,
                    existing.material_delta,
                    existing.evidence.source,
                    existing.evidence.freshness_seconds,
                )
                if existing_fingerprint != incoming_fingerprint:
                    raise ValueError("conflicting Factory state evidence at identical observed_at rejected")
        factory = FactoryState(
            name=factory_name,
            active=active,
            next=next_value,
            wait=wait,
            material_delta=material_delta,
            evidence=evidence,
            freshness=evidence.freshness_state(),
        )
        company.factories = [item for item in company.factories if item.name != factory.name] + [factory]
        return factory

    company, factory = mutate_company(company_id, apply)
    append_audit(actor=f"factory:{factory.name}", action="ingest_factory_state", level="GREEN", company_id=company_id, result="factory_state_ingested", source_data={"source": evidence.source, "observed_at": observed_at, "freshness_seconds": freshness_seconds, "freshness": factory.freshness.value})
    return company


def append_audit(*, actor: str, action: str, level: str, result: str, company_id: str | None = None, source_data: dict | None = None, failure_state: str | None = None) -> None:
    with connect() as conn:
        conn.execute("INSERT INTO audit_log(created_at,company_id,actor,action,level,source_data,result,failure_state) VALUES(?,?,?,?,?,?,?,?)", (now_iso(), company_id, actor, action, level, json.dumps(source_data or {}, ensure_ascii=False), result, failure_state))
        conn.commit()


def list_audit(limit: int = 80) -> list[dict]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [dict(row) for row in rows]


def bootstrap_if_empty() -> None:
    with connect() as conn:
        if conn.execute("SELECT COUNT(*) AS n FROM companies").fetchone()["n"]:
            return
    for company in build_seed_companies(now_iso()):
        save_company(company)
