"""Native API facade for the ObraSignal mobile clients."""
from datetime import datetime, timezone
from flask import Blueprint, jsonify, request

import preload as _preload
from preload import APP, _deadline_dt
from company_profile import load_profile, save_profile, derive_profile

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
    c = _db()
    c.execute("SELECT 1").fetchone()
    c.close()
    return jsonify({"ok": True, "service": "obrasignal-api", "version": "1", "time": _iso_now()})


@bp.route("/profile", methods=["GET", "POST"])
def profile():
    if request.method == "GET":
        return jsonify({"profile": load_profile(), "generated_at": _iso_now()})
    payload = request.get_json(silent=True) or {}
    current = load_profile()
    merged = dict(current)
    allowed = {"name", "activity", "keywords", "countries", "cpv_prefixes", "min_value", "max_value", "exclude_keywords"}
    merged.update({k: payload[k] for k in allowed if k in payload})
    normalized = derive_profile(str(merged.get("activity") or ""), merged)
    saved = save_profile(normalized)
    return jsonify({"ok": True, "profile": saved, "generated_at": _iso_now()})


@bp.route("/stats", methods=["GET"])
def stats():
    c = _db()
    total = c.execute("SELECT COUNT(*) FROM tenders").fetchone()[0]
    high = c.execute("SELECT COUNT(*) FROM tenders WHERE score >= 75").fetchone()[0]
    open_count = c.execute("SELECT COUNT(*) FROM tenders WHERE deadline IS NULL OR deadline = '' OR datetime(deadline) >= datetime('now')").fetchone()[0]
    new24 = c.execute("SELECT COUNT(*) FROM tenders WHERE julianday(first_seen) >= julianday('now','-1 day')").fetchone()[0]
    last = c.execute("SELECT finished_at FROM sync_runs ORDER BY id DESC LIMIT 1").fetchone()
    c.close()
    return jsonify({"total": total, "high": high, "open": open_count, "new24": new24, "last_sync": last[0] if last else None})


@bp.route("/opportunities", methods=["GET"])
def opportunities():
    q = (request.args.get("q") or "").strip().lower()
    source = (request.args.get("source") or "").strip().upper()
    minscore = max(0, min(100, int(request.args.get("minscore", 0) or 0)))
    limit = max(1, min(100, int(request.args.get("limit", 30) or 30)))
    open_only = request.args.get("open", "0").lower() in ("1", "true", "yes")
    c = _db()
    clauses = ["score >= ?"]
    params = [minscore]
    if source:
        clauses.append("source = ?")
        params.append(source)
    if open_only:
        clauses.append("(deadline IS NULL OR deadline = '' OR datetime(deadline) >= datetime('now'))")
    if q:
        clauses.append("(lower(title) LIKE ? OR lower(description) LIKE ? OR lower(buyer) LIKE ? OR lower(cpv) LIKE ?)")
        needle = f"%{q}%"
        params.extend([needle, needle, needle, needle])
    sql = "SELECT * FROM tenders WHERE " + " AND ".join(clauses) + " ORDER BY score DESC, publication_date DESC LIMIT ?"
    params.append(limit)
    rows = [_row(r) for r in c.execute(sql, params).fetchall()]
    c.close()
    return jsonify({"items": rows, "count": len(rows), "generated_at": _iso_now(), "filters": {"q": q, "minscore": minscore, "source": source, "open_only": open_only}})


@bp.route("/opportunities/<int:tender_id>", methods=["GET"])
def opportunity(tender_id):
    c = _db()
    row = c.execute("SELECT * FROM tenders WHERE id = ?", (tender_id,)).fetchone()
    c.close()
    if not row:
        return jsonify({"error": "not_found"}), 404
    return jsonify(_row(row))


APP.register_blueprint(bp)
