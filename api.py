"""Native-app API facade for ObraSignal.

The web dashboard remains in app.py/preload.py. This module exposes a small,
stable JSON API for the future iOS/Android client without putting a browser
inside the app.
"""
from datetime import datetime, timezone
from flask import Blueprint, jsonify, request

from preload import APP, _deadline_dt

bp = Blueprint("mobile_api", __name__, url_prefix="/api/v1")


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


@bp.after_request
def _headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Cache-Control"] = "no-store"
    return response


@bp.route("/health", methods=["GET"])
def health():
    return jsonify({"ok": True, "service": "obrasignal-api", "time": _iso_now()})


@bp.route("/stats", methods=["GET"])
def stats():
    c = APP.view_functions["index"].__globals__["db"]()
    total = c.execute("SELECT COUNT(*) FROM tenders").fetchone()[0]
    high = c.execute("SELECT COUNT(*) FROM tenders WHERE score >= 75").fetchone()[0]
    cutoff = datetime.now(timezone.utc).timestamp() - 86400
    # first_seen is ISO text; use SQLite's date comparison for the dashboard metric.
    new24 = c.execute("SELECT COUNT(*) FROM tenders WHERE first_seen >= datetime('now','-1 day')").fetchone()[0]
    last = c.execute("SELECT finished_at FROM sync_runs ORDER BY id DESC LIMIT 1").fetchone()
    c.close()
    return jsonify({"total": total, "high": high, "new24": new24, "last_sync": last[0] if last else None})


@bp.route("/opportunities", methods=["GET"])
def opportunities():
    q = (request.args.get("q") or "").strip().lower()
    source = (request.args.get("source") or "").strip().upper()
    minscore = max(0, min(100, int(request.args.get("minscore", 0) or 0)))
    limit = max(1, min(100, int(request.args.get("limit", 30) or 30)))
    c = APP.view_functions["index"].__globals__["db"]()
    clauses = ["score >= ?"]
    params = [minscore]
    if source:
        clauses.append("source = ?"); params.append(source)
    if q:
        clauses.append("(lower(title) LIKE ? OR lower(description) LIKE ? OR lower(buyer) LIKE ?)")
        needle = f"%{q}%"; params.extend([needle, needle, needle])
    sql = "SELECT * FROM tenders WHERE " + " AND ".join(clauses) + " ORDER BY score DESC, publication_date DESC LIMIT ?"
    params.append(limit)
    rows = [_row(r) for r in c.execute(sql, params).fetchall()]
    c.close()
    return jsonify({"items": rows, "count": len(rows), "generated_at": _iso_now()})


@bp.route("/opportunities/<int:tender_id>", methods=["GET"])
def opportunity(tender_id):
    c = APP.view_functions["index"].__globals__["db"]()
    row = c.execute("SELECT * FROM tenders WHERE id = ?", (tender_id,)).fetchone()
    c.close()
    if not row:
        return jsonify({"error": "not_found"}), 404
    return jsonify(_row(row))


APP.register_blueprint(bp)
