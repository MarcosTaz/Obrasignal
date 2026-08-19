"""Production compatibility layer for ObraSignal."""
import time
from datetime import datetime, timezone, timedelta

import app as _app
from national_sources import fetch_national_sources
from notification_events import record_new_opportunities
from source_health import ensure_source_health, get_source_cursor, record_source_result, set_source_cursor, source_health_snapshot
from latency_metrics import ensure_latency_table, record_stage, latency_snapshot, latency_summary
from latency_health import latency_health
from ted_client import post_json
from auth_context import configured_identity, InvalidTokenError
from account_registry import list_active_accounts
from funnel_integration import persist_and_classify
from decision_dashboard import get_presented_decision
from radar_decision_feed import enrich_rows
from radar_web import render_radar_page
from opportunity_web import render_opportunity_detail

APP = _app.APP
_original_fetch_base = _app.fetch_base
_original_sync_once = getattr(_app, "sync_once", None)


@APP.before_request
def _protect_legacy_routes():
    path = _app.request.path
    if path == "/":
        return _app.redirect("https://marcostaz.github.io/Obrasignal/", code=302)
    metric_paths = ("/api/v1/source-health", "/api/v1/latency", "/api/v1/latency-health")
    protected = (path == "/sync" or path == "/radar" or path.startswith("/opportunity/") or path == "/api/v1/tenders" or path in metric_paths)
    if not protected:
        return None
    if path.startswith("/api/v1/") and path not in metric_paths and path != "/api/v1/tenders":
        return None
    try:
        identity = configured_identity()
    except (RuntimeError, InvalidTokenError):
        return _app.jsonify({"error": "authentication_required"}), 401
    _app.request.obrasignal_identity = identity
    return None


def _deadline_dt(value):
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
    identity = getattr(_app.request, "obrasignal_identity", None) or configured_identity()
    limit = max(1, min(100, int(_app.request.args.get("limit", 20) or 20)))
    minscore = max(0, min(100, int(_app.request.args.get("minscore", 0) or 0)))
    conn = _app.db()
    try:
        rows = conn.execute("SELECT * FROM tenders WHERE score >= ? ORDER BY score DESC, publication_date DESC LIMIT ?", (minscore, limit)).fetchall()
        items = enrich_rows(conn, rows, account_id=identity.account_id)
        return _app.jsonify(items=items, count=len(items), minscore=minscore, limit=limit, account_id=identity.account_id)
    finally:
        conn.close()


@APP.get("/radar")
def radar_page():
    identity = getattr(_app.request, "obrasignal_identity", None) or configured_identity()
    try:
        minscore = max(0, min(100, int(_app.request.args.get("minscore", 0) or 0)))
    except (TypeError, ValueError):
        minscore = 0
    conn = _app.db()
    try:
        rows = conn.execute("SELECT * FROM tenders WHERE score >= ? ORDER BY score DESC, publication_date DESC LIMIT 100", (minscore,)).fetchall()
        items = enrich_rows(conn, rows, account_id=identity.account_id)
        return render_radar_page(items, minscore=minscore)
    finally:
        conn.close()


def _record_account_decisions(conn):
    """Evaluate the just-synced tenders for every active account."""
    run = conn.execute("SELECT finished_at FROM sync_runs ORDER BY id DESC LIMIT 1").fetchone()
    if not run or not run["finished_at"]:
        return 0
    rows = conn.execute("SELECT * FROM tenders WHERE last_seen=?", (run["finished_at"],)).fetchall()
    accounts = list_active_accounts(conn) or [configured_identity().account_id]
    recorded = 0
    for account_id in accounts:
        for row in rows:
            persist_and_classify(conn, dict(row), True, account_id=account_id)
            recorded += 1
    return recorded


def _record_account_events(conn):
    accounts = list_active_accounts(conn) or [configured_identity().account_id]
    events = []
    for account_id in accounts:
        events.extend(record_new_opportunities(conn, account_id=account_id, min_score=75))
    return events


def sync_once_with_events(*args, **kwargs):
    if _original_sync_once is None:
        return None
    started = time.perf_counter()
    started_at = datetime.now(timezone.utc).isoformat()
    result = _original_sync_once(*args, **kwargs)
    conn = _app.db()
    try:
        decisions = _record_account_decisions(conn)
        events = _record_account_events(conn)
        duration_ms = int((time.perf_counter() - started) * 1000)
        record_stage(conn, "PIPELINE", "sync_and_events", started_at, duration_ms, len(events))
    finally:
        conn.close()
    return {"sync": result, "decisions": decisions, "new_events": events}


@APP.get("/opportunity/<int:tender_id>")
def opportunity_detail(tender_id):
    identity = getattr(_app.request, "obrasignal_identity", None) or configured_identity()
    conn = _app.db()
    row = conn.execute("SELECT * FROM tenders WHERE id=?", (tender_id,)).fetchone()
    if row is None:
        conn.close()
        return "Oportunidade não encontrada", 404
    item = dict(row)
    decision = get_presented_decision(conn, item.get("source"), item.get("external_id"), account_id=identity.account_id)
    conn.close()
    return render_opportunity_detail(item, decision)


if _original_sync_once is not None:
    _app.sync_once = sync_once_with_events
