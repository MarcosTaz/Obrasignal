"""Lifecycle-aware commercial read model for legacy ObraSignal surfaces.

The canonical ``tenders`` table remains historical. Current commercial surfaces
must hide rows explicitly marked non-actionable by a source lifecycle update,
while direct detail remains available with the lifecycle state attached.

This module is installed additively at the production WSGI boundary so the
legacy ingestion/ranking core does not need a rewrite.
"""
from datetime import datetime, timezone, timedelta

import app as _app
from auth_context import configured_identity
from decision_dashboard import get_presented_decision
from funnel_integration import persist_and_classify
from opportunity_lifecycle import ensure_lifecycle_table
from opportunity_web import render_opportunity_detail
from radar_decision_feed import enrich_rows
from radar_web import render_radar_page


def _ensure(conn):
    ensure_lifecycle_table(conn)


def query_tenders(market, q, country, minscore, limit=60):
    """Legacy list read that excludes explicit source tombstones."""
    conn = _app.db()
    try:
        _ensure(conn)
        where = ["COALESCE(lc.is_actionable,1)=1"]
        params = []
        if market in ("PT", "EU"):
            where.append("t.market=?")
            params.append(market)
        if q:
            where.append("(t.title LIKE ? OR t.description LIKE ? OR t.buyer LIKE ? OR t.cpv LIKE ?)")
            params += [f"%{q}%"] * 4
        if country:
            where.append("t.country=?")
            params.append(country.upper())
        if minscore:
            where.append("t.score>=?")
            params.append(int(minscore))
        params.append(limit)
        rows = conn.execute(
            "SELECT t.* FROM tenders t "
            "LEFT JOIN opportunity_lifecycle lc "
            "ON lc.source=t.source AND lc.external_id=t.external_id "
            f"WHERE {' AND '.join(where)} "
            "ORDER BY t.score DESC, t.publication_date DESC LIMIT ?",
            params,
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def stats_for(market):
    """Legacy dashboard stats count current actionable rows only."""
    conn = _app.db()
    try:
        _ensure(conn)
        where = ["COALESCE(lc.is_actionable,1)=1"]
        params = []
        if market in ("PT", "EU"):
            where.append("t.market=?")
            params.append(market)
        base = (
            " FROM tenders t LEFT JOIN opportunity_lifecycle lc "
            "ON lc.source=t.source AND lc.external_id=t.external_id WHERE "
            + " AND ".join(where)
        )
        total = conn.execute("SELECT COUNT(*) n" + base, params).fetchone()["n"]
        high = conn.execute("SELECT COUNT(*) n" + base + " AND t.score>=75", params).fetchone()["n"]
        new24 = conn.execute(
            "SELECT COUNT(*) n" + base + " AND t.first_seen>=?",
            params + [(datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()],
        ).fetchone()["n"]
        last = conn.execute("SELECT MAX(finished_at) v FROM sync_runs").fetchone()["v"]
        return dict(total=total, new24=new24, high=high, last=last or "nunca")
    finally:
        conn.close()


def api_radar():
    identity = getattr(_app.request, "obrasignal_identity", None) or configured_identity()
    limit = max(1, min(100, int(_app.request.args.get("limit", 20) or 20)))
    minscore = max(0, min(100, int(_app.request.args.get("minscore", 0) or 0)))
    conn = _app.db()
    try:
        _ensure(conn)
        rows = conn.execute(
            """SELECT t.* FROM tenders t
               LEFT JOIN opportunity_lifecycle lc
                 ON lc.source=t.source AND lc.external_id=t.external_id
               WHERE t.score >= ? AND COALESCE(lc.is_actionable,1)=1
               ORDER BY t.score DESC, t.publication_date DESC LIMIT ?""",
            (minscore, limit),
        ).fetchall()
        items = enrich_rows(conn, rows, account_id=identity.account_id)
        return _app.jsonify(
            items=items,
            count=len(items),
            minscore=minscore,
            limit=limit,
            account_id=identity.account_id,
        )
    finally:
        conn.close()


def radar_page():
    identity = getattr(_app.request, "obrasignal_identity", None) or configured_identity()
    try:
        minscore = max(0, min(100, int(_app.request.args.get("minscore", 0) or 0)))
    except (TypeError, ValueError):
        minscore = 0
    conn = _app.db()
    try:
        _ensure(conn)
        rows = conn.execute(
            """SELECT t.* FROM tenders t
               LEFT JOIN opportunity_lifecycle lc
                 ON lc.source=t.source AND lc.external_id=t.external_id
               WHERE t.score >= ? AND COALESCE(lc.is_actionable,1)=1
               ORDER BY t.score DESC, t.publication_date DESC LIMIT 100""",
            (minscore,),
        ).fetchall()
        items = enrich_rows(conn, rows, account_id=identity.account_id)
        return render_radar_page(items, minscore=minscore)
    finally:
        conn.close()


def record_account_decisions(conn, *, list_active_accounts):
    """Classify only currently actionable rows from the just-completed sync."""
    _ensure(conn)
    run = conn.execute("SELECT finished_at FROM sync_runs ORDER BY id DESC LIMIT 1").fetchone()
    if not run or not run["finished_at"]:
        return 0
    rows = conn.execute(
        """SELECT t.* FROM tenders t
           LEFT JOIN opportunity_lifecycle lc
             ON lc.source=t.source AND lc.external_id=t.external_id
           WHERE t.last_seen=? AND COALESCE(lc.is_actionable,1)=1""",
        (run["finished_at"],),
    ).fetchall()
    accounts = list_active_accounts(conn) or [configured_identity().account_id]
    recorded = 0
    for account_id in accounts:
        for row in rows:
            persist_and_classify(conn, dict(row), True, account_id=account_id)
            recorded += 1
    return recorded


def opportunity_detail(tender_id):
    """Preserve history while presenting the publisher's current lifecycle state."""
    identity = getattr(_app.request, "obrasignal_identity", None) or configured_identity()
    conn = _app.db()
    try:
        _ensure(conn)
        row = conn.execute(
            """SELECT t.*, COALESCE(lc.is_actionable,1) AS is_actionable,
                      lc.lifecycle_status, lc.lifecycle_reason,
                      lc.source_updated_at AS lifecycle_source_updated_at,
                      lc.last_observed AS lifecycle_last_observed
               FROM tenders t
               LEFT JOIN opportunity_lifecycle lc
                 ON lc.source=t.source AND lc.external_id=t.external_id
               WHERE t.id=?""",
            (tender_id,),
        ).fetchone()
        if row is None:
            return "Oportunidade não encontrada", 404
        item = dict(row)
        decision = get_presented_decision(
            conn,
            item.get("source"),
            item.get("external_id"),
            account_id=identity.account_id,
        )
        return render_opportunity_detail(item, decision)
    finally:
        conn.close()


def install(preload_module):
    """Install lifecycle-aware readers without changing legacy write paths."""
    _app.query_tenders = query_tenders
    _app.stats_for = stats_for
    preload_module._record_account_decisions = lambda conn: record_account_decisions(
        conn, list_active_accounts=preload_module.list_active_accounts
    )

    # Flask stores the route's original function object at decoration time, so
    # replace only the legacy view functions that must consume current lifecycle.
    replacements = {
        "api_radar": api_radar,
        "radar_page": radar_page,
        "opportunity_detail": opportunity_detail,
    }
    for endpoint, view in replacements.items():
        if endpoint in _app.APP.view_functions:
            _app.APP.view_functions[endpoint] = view
    return replacements
