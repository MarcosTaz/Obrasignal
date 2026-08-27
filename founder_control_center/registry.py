from __future__ import annotations

import json
import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .models import ApplicationState, CompanyManifest, Evidence, FactoryState, Metric, RepositoryState, Risk, TruthState
from .seed import build_seed_companies

DB_PATH = os.getenv("FCC_DB", str(Path(__file__).with_name("founder_control_center.db")))


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
        conn.commit()
    bootstrap_if_empty()


def _evidence(value):
    return Evidence(**value) if value else None


def _metric(value):
    if not value:
        return Metric("unknown", "Unknown")
    value = dict(value)
    value["state"] = TruthState(value.get("state", "UNKNOWN"))
    value["evidence"] = _evidence(value.get("evidence"))
    return Metric(**value)


def _from_payload(payload: dict) -> CompanyManifest:
    repo = dict(payload.get("repository") or {})
    repo["ci"] = TruthState(repo.get("ci", "UNKNOWN"))
    repo["evidence"] = _evidence(repo.get("evidence"))
    app = dict(payload.get("application") or {})
    app["deployment"] = TruthState(app.get("deployment", "UNKNOWN"))
    app["health"] = TruthState(app.get("health", "UNKNOWN"))
    app["evidence"] = _evidence(app.get("evidence"))
    risks = []
    for item in payload.get("risks", []):
        item = dict(item); item["evidence"] = _evidence(item.get("evidence")); risks.append(Risk(**item))
    factories = []
    for item in payload.get("factories", []):
        item = dict(item); item["evidence"] = _evidence(item.get("evidence")); factories.append(FactoryState(**item))
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


def list_companies() -> list[CompanyManifest]:
    with connect() as conn:
        rows = conn.execute("SELECT payload FROM companies ORDER BY id").fetchall()
    return [_from_payload(json.loads(row["payload"])) for row in rows]


def get_company(company_id: str) -> CompanyManifest | None:
    with connect() as conn:
        row = conn.execute("SELECT payload FROM companies WHERE id=?", (company_id,)).fetchone()
    return _from_payload(json.loads(row["payload"])) if row else None


def save_company(company: CompanyManifest) -> None:
    company.last_update = company.last_update or now_iso()
    with connect() as conn:
        conn.execute("INSERT INTO companies(id,payload,updated_at) VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload,updated_at=excluded.updated_at", (company.id, json.dumps(company.to_dict(), ensure_ascii=False), now_iso()))
        conn.commit()


def register_company_stub(*, company_id: str, name: str, mission: str, kind: str = "company", repository_full_name: str | None = None, application_url: str | None = None) -> CompanyManifest:
    """Register a future company without inventing operational truth."""
    company_id = company_id.strip().lower()
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,62}[a-z0-9]", company_id):
        raise ValueError("company_id must be a 3-64 character lowercase slug")
    name = name.strip()
    mission = mission.strip()
    if not name or not mission:
        raise ValueError("name and mission are required")
    if get_company(company_id):
        raise ValueError("company_id already exists")
    evidence = Evidence(source="founder_manual_registry", observed_at=now_iso(), freshness_seconds=None, kind="manual_registry", detail="Identity fields are founder-provided. Operational status remains UNKNOWN until canonical adapters provide evidence.")
    company = CompanyManifest(
        id=company_id, name=name[:120], mission=mission[:1000], kind=(kind or "company")[:80],
        status="UNKNOWN", stage="UNKNOWN", active="Connect canonical truth sources", next="Establish ACTIVE / NEXT / WAIT from evidence", wait="NONE",
        repository=RepositoryState(full_name=repository_full_name.strip() if repository_full_name else None, evidence=evidence),
        application=ApplicationState(name=name, url=application_url.strip() if application_url else None, evidence=evidence),
        last_update=now_iso(), data_freshness=TruthState.UNKNOWN, synthetic=False,
        source_note="Registered manually; business, application and repository health remain UNKNOWN until source adapters prove them.",
    )
    save_company(company)
    append_audit(actor="founder", action="register_company", level="GREEN", company_id=company_id, result="registered_unknown_truth", source_data={"repository": repository_full_name, "application_url": application_url})
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
