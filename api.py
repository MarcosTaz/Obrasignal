"""Native API facade for the ObraSignal mobile clients."""
from datetime import datetime, timezone
import os
from urllib.parse import urlsplit, urlunsplit
from flask import Blueprint, jsonify, request
from jwt import InvalidTokenError

import preload as _preload
from preload import APP, _deadline_dt
from auth_context import configured_identity
from company_profile import load_profile, save_profile, derive_profile
from notification_events import ensure_event_table
from source_registry import SOURCES
from account_registry import ensure_account
from decision_log import ensure_decision_table
from opportunity_workflow import get_workflow, set_workflow, workflow_counts

bp = Blueprint("mobile_api", __name__, url_prefix="/api/v1")


def _db():
    return _preload._app.db()


def _iso_now():
    return datetime.now(timezone.utc).isoformat()


def _identity():
    return configured_identity()


def _cors_origin():
    origin = (os.getenv("OBRASIGNAL_CORS_ORIGIN") or "https://marcostaz.github.io").strip()
    auth_mode = (os.getenv("OBRASIGNAL_AUTH_MODE") or "development").strip().lower()
    if auth_mode == "development":
        return "*" if origin == "*" else origin
    if not origin or origin == "*":
        raise RuntimeError("OBRASIGNAL_CORS_ORIGIN must be configured for provider mode")
    parsed = urlsplit(origin)
    if not parsed.scheme or not parsed.netloc:
        raise RuntimeError("OBRASIGNAL_CORS_ORIGIN must be a valid browser origin")
    return urlunsplit((parsed.scheme, parsed.netloc, "", "", ""))


def _apply_cors(response):
    try:
        origin = _cors_origin()
    except RuntimeError:
        origin = None
    if origin:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Vary"] = "Origin"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-ObraSignal-Version, Authorization"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Max-Age"] = "600"
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-ObraSignal-API"] = "v1"
    response.headers["X-ObraSignal-Build"] = os.getenv("OBRASIGNAL_BUILD", "unversioned")
    return response


@bp.before_request
def _require_identity():
    if request.method == "OPTIONS":
        return _apply_cors(APP.response_class("", status=204, mimetype="text/plain"))
    if request.endpoint == "mobile_api.health":
        return None
    try:
        identity = _identity()
    except (RuntimeError, InvalidTokenError):
        return jsonify({"error": "authentication_required"}), 401
    request.obrasignal_identity = identity
    conn = _db()
    try:
        ensure_account(conn, identity.account_id)
    finally:
        conn.close()
    return None


@bp.after_request
def _headers(response):
    return _apply_cors(response)


def _deadline_state(value):
    dt = _deadline_dt(value)
    if not dt:
        return {"state": "unknown", "label": "Prazo não indicado", "days_remaining": None}
    days = (dt - datetime.now(timezone.utc)).total_seconds() / 86400
    if days < 0:
        return {"state": "closed", "label": "Terminado", "days_remaining": int(days)}
    if days <= 2:
        return {"state": "urgent", "label": "Urgente", "days_remaining": int(days)}
    if days <= 7:
        return {"state": "urgent", "label": "Prazo curto", "days_remaining": int(days)}
    return {"state": "open", "label": "Aberto", "days_remaining": int(days)}


def _row(row, decision=None, workflow=None):
    d = dict(row)
    d["deadline_status"] = _deadline_state(d.get("deadline"))
    d["is_open"] = d["deadline_status"]["state"] in ("open", "urgent")
    if decision:
        d["account_decision"] = decision.get("decision")
        d["account_reason"] = decision.get("reason")
        d["account_score"] = decision.get("score")
        d["account_rule_version"] = decision.get("rule_version")
        d["account_decided_at"] = decision.get("decided_at")
        d["explanation"] = decision.get("features", {}).get("explanation")
        d["economic_fit"] = decision.get("features", {}).get("economic_fit")
        d["capability_evidence"] = decision.get("features", {}).get("capability_evidence")
        d["hard_capability_blockers"] = decision.get("features", {}).get("hard_capability_blockers", [])
        d["profile_score"] = decision.get("features", {}).get("profile_score", d.get("profile_score"))
        d["lot_score"] = decision.get("features", {}).get("lot_score", d.get("lot_score"))
        d["geography"] = decision.get("features", {}).get("geography")
    else:
        d["account_decision"] = None
        d["account_reason"] = None
        d["account_score"] = None
    d["decision_score"] = d.get("account_score")
    d["decision_reason"] = d.get("account_reason")
    d["workflow"] = workflow or {"status": "NEW", "note": None, "updated_at": None}
    return d


def _decision_priority(decision):
    return {"QUALIFIED": 0, "RELEVANT": 0, "REVIEW": 1, "UNKNOWN": 2, "REJECT": 3}.get(decision or "UNKNOWN", 2)


def _latest_decisions(conn, account_id, external_ids):
    ensure_decision_table(conn)
    if not external_ids:
        return {}
    placeholders = ",".join("?" for _ in external_ids)
    rows = conn.execute(
        f"""SELECT d.* FROM opportunity_decisions d
            JOIN (SELECT source, external_id, MAX(id) AS max_id FROM opportunity_decisions
                  WHERE account_id=? AND external_id IN ({placeholders}) GROUP BY source, external_id) latest
            ON latest.max_id = d.id""",
        (account_id, *external_ids),
    ).fetchall()
    result = {}
    import json
    for row in rows:
        item = dict(row)
        item["features"] = json.loads(item.pop("features_json") or "{}")
        result[(item["source"], item["external_id"])] = item
    return result


@bp.route("/health", methods=["GET"])
def health():
    c = _db()
    c.execute("SELECT 1").fetchone()
    c.close()
    return jsonify({"ok": True, "service": "obrasignal-api", "version": "1", "build": os.getenv("OBRASIGNAL_BUILD", "unversioned"), "time": _iso_now()})


@bp.route("/sources", methods=["GET"])
def sources():
    identity = request.obrasignal_identity
    items = [{"name": name, **meta} for name, meta in sorted(SOURCES.items(), key=lambda pair: (pair[1].get("priority", 99), pair[0]))]
    return jsonify({"items": items, "count": len(items), "generated_at": _iso_now(), "account_id": identity.account_id})


_PROFILE_FIELDS = {"name", "activity", "keywords", "countries", "cpv_prefixes", "min_value", "max_value", "economic_min_score", "min_deadline_days", "max_deadline_days", "preferred_procedure_types", "excluded_procedure_types", "exclude_keywords", "regions", "geographic_radius_km", "services", "capability_tags", "project_scales", "certifications", "hard_exclusions"}


@bp.route("/profile", methods=["GET", "POST"])
def profile():
    identity = request.obrasignal_identity
    if request.method == "GET":
        current = load_profile(identity.account_id)
        return jsonify({"profile": current, "account_id": identity.account_id, "authenticated": identity.authenticated, "generated_at": _iso_now()})
    payload = request.get_json(silent=True) or {}
    current = load_profile(identity.account_id)
    merged = dict(current)
    merged.update({k: payload[k] for k in _PROFILE_FIELDS if k in payload})
    normalized = derive_profile(str(merged.get("activity") or ""), merged)
    normalized["account_id"] = identity.account_id
    saved = save_profile(normalized, account_id=identity.account_id)
    return jsonify({"ok": True, "profile": saved, "account_id": identity.account_id, "authenticated": identity.authenticated, "generated_at": _iso_now()})


@bp.route("/alerts", methods=["GET"])
def alerts():
    identity = request.obrasignal_identity
    limit = max(1, min(50, int(request.args.get("limit", 20) or 20)))
    unread_only = request.args.get("unread", "0").lower() in ("1", "true", "yes")
    c = _db()
    ensure_event_table(c)
    where = "WHERE e.account_id=? AND e.event_type='new_high_match'"
    params = [identity.account_id]
    if unread_only:
        where += " AND e.delivered_at IS NULL"
    params.append(limit)
    rows = c.execute(f"""SELECT e.id AS event_id, e.event_key, e.score, e.created_at, e.delivered_at,
                   t.id, t.title, t.country, t.source, t.url, t.deadline, t.profile_reason, t.profile_score, t.external_id
            FROM opportunity_events e LEFT JOIN tenders t ON t.id=e.tender_id
            {where} ORDER BY e.created_at DESC LIMIT ?""", params).fetchall()
    decisions = _latest_decisions(c, identity.account_id, [r["external_id"] for r in rows])
    items = []
    for r in rows:
        d = _row(r, decisions.get((r["source"], r["external_id"])), get_workflow(c, identity.account_id, r["source"], r["external_id"]))
        d.update({"event_id": r["event_id"], "event_key": r["event_key"], "score": r["score"], "created_at": r["created_at"], "delivered_at": r["delivered_at"], "delivery_state": "delivered" if r["delivered_at"] else "new"})
        items.append(d)
    c.close()
    items.sort(key=lambda item: (_decision_priority(item.get("account_decision")), -(item.get("account_score") or item.get("score") or 0), item.get("created_at") or ""))
    return jsonify({"items": items[:limit], "count": len(items[:limit]), "generated_at": _iso_now(), "account_id": identity.account_id})


@bp.route("/alerts/<int:event_id>/delivered", methods=["POST"])
def alert_delivered(event_id):
    identity = request.obrasignal_identity
    c = _db()
    ensure_event_table(c)
    now = _iso_now()
    cur = c.execute("UPDATE opportunity_events SET delivered_at=? WHERE id=? AND account_id=?", (now, event_id, identity.account_id))
    c.commit()
    c.close()
    if not cur.rowcount:
        return jsonify({"error": "not_found"}), 404
    return jsonify({"ok": True, "event_id": event_id, "delivered_at": now})


@bp.route("/stats", methods=["GET"])
def stats():
    identity = request.obrasignal_identity
    c = _db()
    ensure_decision_table(c)
    latest = """JOIN (
        SELECT od.source, od.external_id, MAX(od.id) AS max_id
        FROM opportunity_decisions od
        WHERE od.account_id=?
        GROUP BY od.source, od.external_id
    ) latest ON latest.max_id=d.id"""
    base = f"FROM tenders t JOIN opportunity_decisions d ON d.source=t.source AND d.external_id=t.external_id {latest} WHERE d.account_id=?"
    params = [identity.account_id, identity.account_id]
    total = c.execute(f"SELECT COUNT(*) {base}", params).fetchone()[0]
    high = c.execute(f"SELECT COUNT(*) {base} AND d.score >= 75", params).fetchone()[0]
    open_count = c.execute(f"SELECT COUNT(*) {base} AND (t.deadline IS NULL OR t.deadline='' OR datetime(t.deadline)>=datetime('now'))", params).fetchone()[0]
    new24 = c.execute(f"SELECT COUNT(*) {base} AND julianday(t.first_seen)>=julianday('now','-1 day')", params).fetchone()[0]
    last = c.execute("SELECT finished_at FROM sync_runs ORDER BY id DESC LIMIT 1").fetchone()
    c.close()
    return jsonify({"total": total, "high": high, "open": open_count, "new24": new24, "last_sync": last[0] if last else None, "account_id": identity.account_id})


@bp.route("/workflow/stats", methods=["GET"])
def workflow_stats():
    identity = request.obrasignal_identity
    c = _db()
    counts = workflow_counts(c, identity.account_id)
    c.close()
    return jsonify({"counts": counts, "account_id": identity.account_id, "generated_at": _iso_now()})


@bp.route("/opportunities", methods=["GET"])
def opportunities():
    identity = request.obrasignal_identity
    q = (request.args.get("q") or "").strip().lower()
    source = (request.args.get("source") or "").strip().upper()
    minscore = max(0, min(100, int(request.args.get("minscore", 0) or 0)))
    limit = max(1, min(100, int(request.args.get("limit", 30) or 30)))
    open_only = request.args.get("open", "0").lower() in ("1", "true", "yes")
    c = _db()
    clauses = ["t.score>=?"]
    params = [minscore]
    if source:
        clauses.append("t.source=?")
        params.append(source)
    if open_only:
        clauses.append("(t.deadline IS NULL OR t.deadline='' OR datetime(t.deadline)>=datetime('now'))")
    if q:
        clauses.append("(lower(t.title) LIKE ? OR lower(t.description) LIKE ? OR lower(t.buyer) LIKE ? OR lower(t.cpv) LIKE ?)")
        needle = f"%{q}%"
        params.extend([needle] * 4)
    sql = "SELECT t.*, d.account_id, d.decision AS account_decision, d.reason AS account_reason, d.score AS account_score, d.rule_version AS account_rule_version, d.decided_at AS account_decided_at, d.features_json FROM tenders t LEFT JOIN (SELECT od.* FROM opportunity_decisions od JOIN (SELECT source, external_id, MAX(id) AS max_id FROM opportunity_decisions WHERE account_id=? GROUP BY source, external_id) latest ON latest.max_id=od.id) d ON d.source=t.source AND d.external_id=t.external_id WHERE " + " AND ".join(clauses) + " ORDER BY CASE d.decision WHEN 'QUALIFIED' THEN 0 WHEN 'RELEVANT' THEN 0 WHEN 'REVIEW' THEN 1 WHEN 'UNKNOWN' THEN 2 WHEN 'REJECT' THEN 3 ELSE 2 END, COALESCE(d.score,t.score) DESC, t.publication_date DESC LIMIT ?"
    params = [identity.account_id, *params, limit]
    rows = []
    import json
    for r in c.execute(sql, params).fetchall():
        item = dict(r)
        features = json.loads(item.pop("features_json") or "{}") if item.get("features_json") else {}
        decision = None if not item.get("account_decision") else {"decision": item.get("account_decision"), "reason": item.get("account_reason"), "score": item.get("account_score"), "rule_version": item.get("account_rule_version"), "decided_at": item.get("account_decided_at"), "features": features}
        rows.append(_row(item, decision, get_workflow(c, identity.account_id, item.get("source"), item.get("external_id"))))
    c.close()
    return jsonify({"items": rows, "count": len(rows), "generated_at": _iso_now(), "account_id": identity.account_id, "filters": {"q": q, "minscore": minscore, "source": source, "open_only": open_only}})


@bp.route("/opportunities/<int:tender_id>", methods=["GET"])
def opportunity(tender_id):
    identity = request.obrasignal_identity
    c = _db()
    ensure_decision_table(c)
    row = c.execute("SELECT * FROM tenders WHERE id=?", (tender_id,)).fetchone()
    if not row:
        c.close()
        return jsonify({"error": "not_found"}), 404
    decision_row = c.execute("SELECT * FROM opportunity_decisions WHERE account_id=? AND source=? AND external_id=? ORDER BY id DESC LIMIT 1", (identity.account_id, row["source"], row["external_id"])).fetchone()
    decision = None
    if decision_row:
        import json
        decision = dict(decision_row)
        decision["features"] = json.loads(decision.pop("features_json") or "{}")
    workflow = get_workflow(c, identity.account_id, row["source"], row["external_id"])
    c.close()
    return jsonify(_row(row, decision, workflow))


@bp.route("/opportunities/<int:tender_id>/workflow", methods=["GET", "POST"])
def opportunity_workflow(tender_id):
    identity = request.obrasignal_identity
    c = _db()
    row = c.execute("SELECT source,external_id FROM tenders WHERE id=?", (tender_id,)).fetchone()
    if not row:
        c.close()
        return jsonify({"error": "not_found"}), 404
    source, external_id = row["source"], row["external_id"]
    if request.method == "GET":
        result = get_workflow(c, identity.account_id, source, external_id)
        c.close()
        return jsonify(result)
    payload = request.get_json(silent=True) or {}
    try:
        result = set_workflow(c, identity.account_id, source, external_id, payload.get("status"), payload.get("note"))
    except ValueError as exc:
        c.close()
        return jsonify({"error": "invalid_workflow_status", "detail": str(exc)}), 400
    c.close()
    return jsonify(result)


APP.register_blueprint(bp)
