"""Production compatibility layer for ObraSignal."""
import time
from datetime import datetime, timezone, timedelta

import app as _app
from national_sources import fetch_national_sources
from notification_events import record_new_opportunities
from profile_scoring import personalized_score
from source_health import ensure_source_health, get_source_cursor, record_source_result, set_source_cursor, source_health_snapshot
from latency_metrics import ensure_latency_table, record_stage, latency_snapshot, latency_summary
from latency_health import latency_health
from ted_client import post_json
from decision_dashboard import get_presented_decision
from radar_decision_feed import enrich_rows
from radar_web import render_radar_page
from opportunity_web import render_opportunity_detail
from profile_page import register_profile_page

APP = _app.APP
_original_fetch_base = _app.fetch_base
_original_sync_once = getattr(_app, "sync_once", None)


def _deadline_dt(value):
    """Compatibility wrapper for API consumers using preload's public surface."""
    return _app.deadline_dt(value)


def _ted_since_date():
    conn = _app.db()
    try:
        watermark = get_source_cursor(conn, "TED")
    finally:
        conn.close()
    if watermark:
        try:
            return (datetime.strptime(watermark, "%Y%m%d") - timedelta(days=1)).strftime("%Y%m%d")
        except ValueError:
            pass
    return (datetime.now(timezone.utc) - timedelta(days=_app.TED_DAYS)).strftime("%Y%m%d")


def _max_ted_publication_date(rows):
    dates = []
    for row in rows:
        value = row.get("publication-date") if isinstance(row, dict) else None
        if not value:
            continue
        text = str(value)
        if len(text) >= 10 and text[:10].count("-") == 2:
            text = text[:10].replace("-", "")
        elif len(text) >= 8:
            text = text[:8]
        if len(text) == 8 and text.isdigit():
            dates.append(text)
    return max(dates) if dates else None


def _fetch_ted_resilient():
    since = _ted_since_date()
    query = f'publication-date>={since} AND (notice-type=cn-standard OR notice-type=cn-social OR notice-type=cn-desg OR notice-type=subco OR notice-type=qu-sy)'
    fields = ['publication-number','notice-title','description-proc','buyer-name','buyer-country','classification-cpv','estimated-value-proc','estimated-value-cur-proc','deadline-receipt-tender-date-lot','deadline-receipt-tender-time-lot','deadline-date-lot','deadline-time-lot','publication-date','notice-type','form-type','main-classification-type-proc','place-of-performance-country-proc','place-of-performance-city-proc','place-of-performance-subdiv-proc','place-of-performance-post-code-proc','place-of-performance-country-lot','place-of-performance-city-lot','place-of-performance-subdiv-proc']
    payload = {'query': query, 'fields': fields, 'limit': 250, 'scope': 'ACTIVE', 'checkQuerySyntax': False, 'paginationMode': 'ITERATION'}
    rows, token = [], None
    for _ in range(_app.TED_MAX_PAGES):
        body = dict(payload)
        if token:
            body['iterationNextToken'] = token
        data = post_json(_app.TED_URL, json=body, timeout=45)
        batch = data.get('notices') or data.get('results') or data.get('content') or []
        rows += batch
        token = data.get('iterationNextToken') or data.get('nextToken') or data.get('nextIterationToken')
        if not token or not batch:
            break
    return rows


def _fetch_ted_with_health(*args, **kwargs):
    started = time.perf_counter()
    started_at = datetime.now(timezone.utc).isoformat()
    conn = _app.db()
    try:
        ensure_source_health(conn)
        ensure_latency_table(conn)
        conn.close()
        rows = _fetch_ted_resilient()
        duration_ms = int((time.perf_counter() - started) * 1000)
        watermark = _max_ted_publication_date(rows)
        conn = _app.db()
        if watermark:
            set_source_cursor(conn, "TED", watermark)
        record_source_result(conn, "TED", success=True, duration_ms=duration_ms, found=len(rows))
        record_stage(conn, "TED", "fetch", started_at, duration_ms, len(rows))
        conn.close()
        return rows
    except Exception as exc:
        duration_ms = int((time.perf_counter() - started) * 1000)
        conn = _app.db()
        record_source_result(conn, "TED", success=False, duration_ms=duration_ms, error=exc)
        record_stage(conn, "TED", "fetch_failed", started_at, duration_ms, 0)
        conn.close()
        raise


_app.fetch_ted = _fetch_ted_with_health


def fetch_base_with_national_sources():
    rows = _original_fetch_base()
    rows.extend(fetch_national_sources())
    return rows


_app.fetch_base = fetch_base_with_national_sources


@APP.get("/api/v1/source-health")
def api_source_health():
    conn = _app.db()
    try:
        return _app.jsonify(items=source_health_snapshot(conn))
    finally:
        conn.close()


@APP.get("/api/v1/latency")
def api_latency():
    conn = _app.db()
    try:
        source = _app.request.args.get("source")
        return _app.jsonify(summary=latency_summary(conn, source), samples=latency_snapshot(conn, source))
    finally:
        conn.close()


@APP.get("/api/v1/latency-health")
def api_latency_health():
    conn = _app.db()
    try:
        source = _app.request.args.get("source")
        return _app.jsonify(items=latency_health(conn, source))
    finally:
        conn.close()


@APP.get("/api/v1/radar")
def api_radar():
    limit = max(1, min(100, int(_app.request.args.get("limit", 20) or 20)))
    minscore = max(0, min(100, int(_app.request.args.get("minscore", 0) or 0)))
    conn = _app.db()
    try:
        rows = conn.execute(
            "SELECT * FROM tenders WHERE score >= ? ORDER BY score DESC, publication_date DESC LIMIT ?",
            (minscore, limit),
        ).fetchall()
        items = enrich_rows(conn, rows)
        return _app.jsonify(items=items, count=len(items), minscore=minscore, limit=limit)
    finally:
        conn.close()


@APP.get("/radar")
def radar_page():
    try:
        minscore = max(0, min(100, int(_app.request.args.get("minscore", 0) or 0)))
    except (TypeError, ValueError):
        minscore = 0

    conn = _app.db()
    try:
        rows = conn.execute(
            "SELECT * FROM tenders WHERE score >= ? ORDER BY score DESC, publication_date DESC LIMIT 100",
            (minscore,),
        ).fetchall()
        items = enrich_rows(conn, rows)
        return render_radar_page(items, minscore=minscore)
    finally:
        conn.close()


def _ensure_profile_columns(conn):
    cols = {r[1] for r in conn.execute("PRAGMA table_info(tenders)").fetchall()}
    if "global_score" not in cols:
        conn.execute("ALTER TABLE tenders ADD COLUMN global_score INTEGER")
    if "profile_score" not in cols:
        conn.execute("ALTER TABLE tenders ADD COLUMN profile_score INTEGER")
    if "profile_reason" not in cols:
        conn.execute("ALTER TABLE tenders ADD COLUMN profile_reason TEXT")
    conn.commit()


def _apply_profile_scores(conn):
    _ensure_profile_columns(conn)
    rows = conn.execute("SELECT * FROM tenders").fetchall()
    for row in rows:
        d = dict(row)
        base = int(d.get("global_score") if d.get("global_score") is not None else d.get("score") or 0)
        score, label, cls, reason = personalized_score(d, base)
        conn.execute("UPDATE tenders SET global_score=?, profile_score=?, score=?, priority_label=?, priority_class=?, profile_reason=?, match_reason=? WHERE id=?", (base, score, score, label, cls, reason, reason, d["id"]))
    conn.commit()


def sync_once_with_events(*args, **kwargs):
    if _original_sync_once is None:
        return None
    started = time.perf_counter()
    started_at = datetime.now(timezone.utc).isoformat()
    result = _original_sync_once(*args, **kwargs)
    conn = _app.db()
    try:
        _apply_profile_scores(conn)
        events = record_new_opportunities(conn, min_score=75)
        duration_ms = int((time.perf_counter() - started) * 1000)
        record_stage(conn, "PIPELINE", "sync_and_events", started_at, duration_ms, len(events))
    finally:
        conn.close()
    return {"sync": result, "new_events": events}


@APP.get("/opportunity/<int:tender_id>")
def opportunity_detail(tender_id):
    conn = _app.db()
    row = conn.execute("SELECT * FROM tenders WHERE id=?", (tender_id,)).fetchone()
    if row is None:
        conn.close()
        return _app.Response("Oportunidade não encontrada", status=404)

    item = dict(row)
    decision = get_presented_decision(conn, item.get("source"), item.get("external_id"))
    conn.close()
    return render_opportunity_detail(item, decision)


register_profile_page(APP)


if _original_sync_once is not None:
    _app.sync_once = sync_once_with_events
