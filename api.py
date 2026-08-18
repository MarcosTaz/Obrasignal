"""Native API facade for the ObraSignal mobile clients."""
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request

import preload as _preload
from preload import APP, _deadline_dt
from company_profile import load_profile, save_profile, derive_profile
from notification_events import ensure_event_table
from source_registry import SOURCES
from company_profile_validation import validate_company_profile

bp = Blueprint("mobile_api", __name__, url_prefix="/api/v1")


def _db():
    return _preload._app.db()


def _iso_now():
    return datetime.now(timezone.utc).isoformat()


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


def _row(row):
    d = dict(row)
    d["deadline_status"] = _deadline_state(d.get("deadline"))
    d["is_open"] = d["deadline_status"]["state"] in ("open", "urgent")
    return d


def _parse_int_arg(name: str, default: int, minimum: int, maximum: int):
    raw = request.args.get(name)
    if raw in (None, ""):
        return default, None
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None, jsonify({"error": "invalid_parameter", "parameter": name, "message": f"{name} deve ser inteiro."})
    if not minimum <= value <= maximum:
        return None, jsonify({"error": "invalid_parameter", "parameter": name, "message": f"{name} deve estar entre {minimum} e {maximum}."})
    return value, None


@bp.after_request
def _headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-ObraSignal-Version"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-ObraSignal-API"] = "v1"
    return response


@bp.route("/health", methods=["GET"])
def health():
    c = _db(); c.execute("SELECT 1").fetchone(); c.close()
    return jsonify({"ok": True, "service": "obrasignal-api", "version": "1", "time": _iso_now()})


@bp.route("/sources", methods=["GET"])
def sources():
    items = []
    for name, meta in sorted(SOURCES.items(), key=lambda pair: (pair[1].get("priority", 99), pair[0])):
        items.append({"name": name, **meta})
    return jsonify({"items": items, "count": len(items), "generated_at": _iso_now()})


_PROFILE_FIELDS = {
    "name", "activity", "keywords", "countries", "cpv_prefixes", "min_value", "max_value",
    "economic_min_score", "min_deadline_days", "max_deadline_days", "preferred_procedure_types",
    "excluded_procedure_types", "exclude_keywords", "regions", "geographic_radius_km", "services",
    "capability_tags", "project_scales", "certifications", "hard_exclusions",
}


@bp.route("/profile", methods=["GET", "POST"])
def profile():
    if request.method == "GET":
        return jsonify({"profile": load_profile(), "generated_at": _iso_now()})
    payload = request.get_json(silent=True)
    if payload is None or not isinstance(payload, dict):
        return jsonify({"error": "invalid_json", "message": "O corpo deve ser um objeto JSON."}), 400

    supplied = {k: payload[k] for k in _PROFILE_FIELDS if k in payload}
    current = load_profile()
    candidate = dict(current)
    candidate.update(supplied)
    normalized = derive_profile(str(candidate.get("activity") or ""), candidate)
    supplied_errors = validate_company_profile(normalized)
    if supplied_errors:
        return jsonify({"error": "INVALID_COMPANY_PROFILE", "errors": supplied_errors}), 400

    try:
        saved = save_profile(normalized)
    except ValueError as exc:
        details = exc.args[0] if exc.args else None
        if isinstance(details, dict) and details.get("code") == "INVALID_COMPANY_PROFILE":
            return jsonify({"error": details["code"], "errors": details.get("errors", [])}), 400
        return jsonify({"error": "invalid_profile", "message": str(exc)}), 400
    return jsonify({"ok": True, "profile": saved, "generated_at": _iso_now()})


@bp.route("/alerts", methods=["GET"])
def alerts():
    limit, error = _parse_int_arg("limit", 20, 1, 50)
    if error:
        return error, 400
    unread_only = request.args.get("unread", "0").lower() in ("1", "true", "yes")
    c = _db(); ensure_event_table(c)
    where = "WHERE e.event_type = 'new_high_match'"
    if unread_only: where += " AND e.delivered_at IS NULL"
    rows = c.execute(f"""SELECT e.id AS event_id, e.event_key, e.score, e.created_at, e.delivered_at,
                   t.id, t.title, t.country, t.source, t.url, t.deadline, t.profile_reason, t.profile_score
            FROM opportunity_events e LEFT JOIN tenders t ON t.id = e.tender_id
            {where} ORDER BY e.created_at DESC LIMIT ?""", (limit,)).fetchall()
    items = []
    for r in rows:
        d = dict(r); d["deadline_status"] = _deadline_state(d.get("deadline")); d["delivery_state"] = "delivered" if d.get("delivered_at") else "new"; items.append(d)
    c.close(); return jsonify({"items": items, "count": len(items), "generated_at": _iso_now()})


@bp.route("/alerts/<int:event_id>/delivered", methods=["POST"])
def alert_delivered(event_id):
    c = _db(); ensure_event_table(c); now = _iso_now()
    cur = c.execute("UPDATE opportunity_events SET delivered_at=? WHERE id=?", (now, event_id)); c.commit(); c.close()
    if not cur.rowcount: return jsonify({"error": "not_found"}), 404
    return jsonify({"ok": True, "event_id": event_id, "delivered_at": now})


@bp.route("/stats", methods=["GET"])
def stats():
    c = _db(); total = c.execute("SELECT COUNT(*) FROM tenders").fetchone()[0]; high = c.execute("SELECT COUNT(*) FROM tenders WHERE score >= 75").fetchone()[0]
    open_count = c.execute("SELECT COUNT(*) FROM tenders WHERE deadline IS NULL OR deadline = '' OR datetime(deadline) >= datetime('now')").fetchone()[0]
    new24 = c.execute("SELECT COUNT(*) FROM tenders WHERE julianday(first_seen) >= julianday('now','-1 day')").fetchone()[0]
    last = c.execute("SELECT finished_at FROM sync_runs ORDER BY id DESC LIMIT 1").fetchone(); c.close()
    return jsonify({"total": total, "high": high, "open": open_count, "new24": new24, "last_sync": last[0] if last else None})


@bp.route("/opportunities", methods=["GET"])
def opportunities():
    q = (request.args.get("q") or "").strip().lower(); source = (request.args.get("source") or "").strip().upper()
    minscore, error = _parse_int_arg("minscore", 0, 0, 100)
    if error:
        return error, 400
    limit, error = _parse_int_arg("limit", 30, 1, 100)
    if error:
        return error, 400
    open_only = request.args.get("open", "0").lower() in ("1", "true", "yes")
    c = _db(); clauses = ["score >= ?"]; params = [minscore]
    if source: clauses.append("source = ?"); params.append(source)
    if open_only: clauses.append("(deadline IS NULL OR deadline = '' OR datetime(deadline) >= datetime('now'))")
    if q:
        clauses.append("(lower(title) LIKE ? OR lower(description) LIKE ? OR lower(buyer) LIKE ? OR lower(cpv) LIKE ?)"); needle = f"%{q}%"; params.extend([needle, needle, needle, needle])
    sql = "SELECT * FROM tenders WHERE " + " AND ".join(clauses) + " ORDER BY score DESC, publication_date DESC LIMIT ?"; params.append(limit)
    rows = [_row(r) for r in c.execute(sql, params).fetchall()]; c.close()
    return jsonify({"items": rows, "count": len(rows), "generated_at": _iso_now(), "filters": {"q": q, "minscore": minscore, "source": source, "open_only": open_only}})


@bp.route("/opportunities/<int:tender_id>", methods=["GET"])
def opportunity(tender_id):
    c = _db(); row = c.execute("SELECT * FROM tenders WHERE id = ?", (tender_id,)).fetchone(); c.close()
    if not row: return jsonify({"error": "not_found"}), 404
    return jsonify(_row(row))


APP.register_blueprint(bp)
