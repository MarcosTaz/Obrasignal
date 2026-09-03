"""Lifecycle-aware compatibility layer for legacy ObraSignal surfaces.

The canonical ``tenders`` table remains historical. Current commercial surfaces
must hide rows that are not effectively actionable, while direct detail remains
available with lifecycle and deadline state attached.

This module is installed additively at the production WSGI boundary so the
legacy ingestion/ranking core does not need a broad rewrite. In addition to the
read-model replacements, it corrects only the temporal component of legacy
commercial scoring for date-only deadlines: calendar precision must not become
an invented midnight timestamp.
"""
from datetime import datetime, timezone, timedelta

import app as _app
from auth_context import configured_identity
from decision_dashboard import get_presented_decision
from funnel_integration import persist_and_classify
from opportunity_lifecycle import actionable_predicate, ensure_lifecycle_table
from opportunity_web import render_opportunity_detail
from account_registry import list_active_accounts
from radar_decision_feed import enrich_rows
from radar_web import render_radar_page


_ORIGINAL_COMMERCIAL_SCORE = _app.commercial_score


def _ensure(conn):
    ensure_lifecycle_table(conn)


def commercial_score(title, description, cpv, deadline=None):
    """Preserve DATE precision when applying the legacy deadline score policy.

    The legacy scorer converts ``YYYY-MM-DD`` to midnight UTC before computing a
    fractional day distance. That can penalize a deadline on the current day as
    expired and can shift the 7/21-day policy boundaries depending on the current
    clock time. For date-only evidence, use calendar-day distance instead. Exact
    timestamps continue through the original scorer unchanged.
    """
    raw = str(deadline or "").strip()
    if len(raw) == 10:
        try:
            deadline_date = datetime.strptime(raw, "%Y-%m-%d").date()
        except ValueError:
            pass
        else:
            days = (deadline_date - datetime.now(timezone.utc).date()).days
            score, _label, _css, reason = _ORIGINAL_COMMERCIAL_SCORE(
                title, description, cpv, None
            )
            if 0 <= days <= 7:
                score += 10
            elif 7 < days <= 21:
                score += 5
            elif days < 0:
                score -= 30
            score = max(0, min(100, score))
            if score >= 75:
                label, css = "PRIORIDADE MÁXIMA", "hot"
            elif score >= 55:
                label, css = "BOA OPORTUNIDADE", "good"
            else:
                label, css = "BAIXA PRIORIDADE", "low"
            if 0 <= days <= 7:
                suffix = "prazo hoje; hora não indicada" if days == 0 else f"prazo em {days} dias; hora não indicada"
                reason += "; " + suffix
            return score, label, css, reason
    return _ORIGINAL_COMMERCIAL_SCORE(title, description, cpv, deadline)


def query_tenders(market, q, country, minscore, limit=60):
    """Legacy list read that returns only effectively actionable rows."""
    conn = _app.db()
    try:
        _ensure(conn)
        where = [actionable_predicate("lc", "t")]
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
    """Legacy dashboard stats count current effectively actionable rows only."""
    conn = _app.db()
    try:
        _ensure(conn)
        where = [actionable_predicate("lc", "t")]
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
            f"""SELECT t.* FROM tenders t
               LEFT JOIN opportunity_lifecycle lc
                 ON lc.source=t.source AND lc.external_id=t.external_id
               WHERE t.score >= ? AND {actionable_predicate('lc', 't')}
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
            f"""SELECT t.* FROM tenders t
               LEFT JOIN opportunity_lifecycle lc
                 ON lc.source=t.source AND lc.external_id=t.external_id
               WHERE t.score >= ? AND {actionable_predicate('lc', 't')}
               ORDER BY t.score DESC, t.publication_date DESC LIMIT 100""",
            (minscore,),
        ).fetchall()
        items = enrich_rows(conn, rows, account_id=identity.account_id)
        return render_radar_page(items, minscore=minscore)
    finally:
        conn.close()


def record_account_decisions(conn, *, list_active_accounts=list_active_accounts):
    """Legacy lifecycle-aware classifier retained for compatibility/tests only.

    Production no longer installs this as the sync decision owner. The canonical
    production owner is ``decision_refresh.record_account_decisions`` which is
    both lifecycle-aware and fingerprint-incremental. Keeping this callable lets
    older direct callers retain the same semantic behavior without silently
    replacing the production refresh strategy during WSGI composition.
    """
    _ensure(conn)
    run = conn.execute("SELECT finished_at FROM sync_runs ORDER BY id DESC LIMIT 1").fetchone()
    if not run or not run["finished_at"]:
        return 0
    rows = conn.execute(
        f"""SELECT t.* FROM tenders t
           LEFT JOIN opportunity_lifecycle lc
             ON lc.source=t.source AND lc.external_id=t.external_id
           WHERE t.last_seen=? AND {actionable_predicate('lc', 't')}""",
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
    """Preserve history while presenting effective current actionability."""
    identity = getattr(_app.request, "obrasignal_identity", None) or configured_identity()
    conn = _app.db()
    try:
        _ensure(conn)
        row = conn.execute(
            f"""SELECT t.*, {actionable_predicate('lc', 't')} AS is_actionable,
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
    """Install lifecycle-aware reads without replacing the decision refresh owner."""
    _app.commercial_score = commercial_score
    _app.query_tenders = query_tenders
    _app.stats_for = stats_for

    # Flask stores the route's original function object at decoration time, so
    # replace only the legacy view functions that must consume current lifecycle.
    # Crucially, do NOT overwrite preload_module._record_account_decisions here:
    # cors_app installs the fingerprint-incremental canonical refresh immediately
    # before this compatibility layer. The previous override caused every source
    # poll to rewrite all observed decisions and contend with customer Radar reads.
    replacements = {
        "api_radar": api_radar,
        "radar_page": radar_page,
        "opportunity_detail": opportunity_detail,
    }
    for endpoint, view in replacements.items():
        if endpoint in _app.APP.view_functions:
            _app.APP.view_functions[endpoint] = view
    return replacements
