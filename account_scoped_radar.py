"""Production account-first projection for the authenticated Radar list.

The historical mobile blueprint retains its broad compatibility contract. The
production WSGI boundary delegates only GET /api/v1/opportunities here so a
Europe-wide Radar starts from the authenticated account's current decisions
instead of scanning the global tender corpus.
"""
from flask import jsonify, request
from jwt import InvalidTokenError

from account_registry import ensure_account
from auth_context import configured_identity
from auth_context_jwt import JwksUnavailableError
from decision_log import current_profile_fingerprint
from opportunity_lifecycle import actionable_predicate, ensure_lifecycle_table
from opportunity_match_pipeline import RULE_VERSION
from opportunity_workflow import get_workflow
from api import _db, _invalid_query, _iso_now, _latest_decisions, _row, _source_contract
from source_health import empty_result_context


def handle_opportunities():
    try:
        identity = configured_identity()
    except JwksUnavailableError:
        return jsonify({"error": "auth_provider_unavailable"}), 503
    except (RuntimeError, InvalidTokenError):
        return jsonify({"error": "authentication_required"}), 401

    try:
        limit = max(1, min(100, int(request.args.get("limit", 20) or 20)))
    except (TypeError, ValueError):
        return _invalid_query("limit")
    try:
        offset = int(request.args.get("offset", 0) or 0)
    except (TypeError, ValueError):
        return _invalid_query("offset")
    if offset < 0 or offset > 100000:
        return _invalid_query("offset")

    market = (request.args.get("market") or "").upper().strip()
    country = (request.args.get("country") or "").upper().strip()
    q = (request.args.get("q") or "").strip().lower()
    source = (request.args.get("source") or "").strip().upper()
    open_only = request.args.get("open", "0").lower() in ("1", "true", "yes")
    raw_minscore = request.args.get("minscore")
    try:
        minscore = int(raw_minscore) if raw_minscore not in (None, "") else None
    except (TypeError, ValueError):
        return _invalid_query("minscore")

    c = _db()
    try:
        ensure_account(c, identity.account_id)
        ensure_lifecycle_table(c)
        profile_fp = current_profile_fingerprint(c, identity.account_id)
        where = [actionable_predicate("lc", "t")]
        params = []
        if market in ("PT", "EU"):
            where.append("(t.market=? OR (t.market IS NULL AND t.country=?))")
            params.extend([market, "PRT"])
        if country:
            where.append("t.country=?")
            params.append(country)
        if q:
            where.append("LOWER(COALESCE(t.title,'') || ' ' || COALESCE(t.description,'') || ' ' || COALESCE(t.buyer,'') || ' ' || COALESCE(t.cpv,'')) LIKE ?")
            params.append(f"%{q}%")
        if source:
            where.append("UPPER(t.source)=?")
            params.append(source)
        if open_only:
            where.append("t.deadline IS NOT NULL AND t.deadline<>'' AND datetime(t.deadline)>=datetime('now')")
        if minscore is not None and minscore > 0:
            where.append("d.score>=?")
            params.append(minscore)

        if profile_fp is None:
            raw_rows = []
        else:
            raw_rows = c.execute(
                f"""SELECT t.*, {actionable_predicate('lc', 't')} AS is_actionable,
                           lc.lifecycle_status, lc.lifecycle_reason,
                           lc.source_updated_at AS lifecycle_source_updated_at,
                           lc.last_observed AS lifecycle_last_observed
                    FROM opportunity_decisions d
                    JOIN (SELECT source, external_id, MAX(id) max_id
                          FROM opportunity_decisions
                          WHERE account_id=? GROUP BY source, external_id) latest
                      ON latest.max_id=d.id
                    JOIN tenders t ON t.source=d.source AND t.external_id=d.external_id
                    LEFT JOIN opportunity_lifecycle lc ON lc.source=t.source AND lc.external_id=t.external_id
                    WHERE d.account_id=? AND d.rule_version=? AND d.profile_fingerprint=?
                      AND {' AND '.join(where)}
                    ORDER BY d.score DESC,
                             COALESCE(t.publication_date,t.first_seen) DESC,
                             t.source ASC, t.external_id ASC, t.id ASC
                    LIMIT ? OFFSET ?""",
                (identity.account_id, identity.account_id, RULE_VERSION, profile_fp, *params, limit + 1, offset),
            ).fetchall()

        has_more = len(raw_rows) > limit
        rows = raw_rows[:limit]
        decisions = _latest_decisions(c, identity.account_id, [r["external_id"] for r in rows])
        items = [
            _row(
                row,
                decisions.get((row["source"], row["external_id"])),
                get_workflow(c, identity.account_id, row["source"], row["external_id"]),
            )
            for row in rows
        ]
        contract = _source_contract(c, source or None)
        empty_context = empty_result_context(contract, len(items))
        page = {
            "limit": limit,
            "offset": offset,
            "has_more": has_more,
            "next_offset": offset + limit if has_more else None,
        }
        return jsonify({
            "items": items,
            "count": len(items),
            "page": page,
            "market": market,
            "source_coverage": contract["summary"],
            "source_health_contract_version": contract["contract_version"],
            "empty_result": empty_context,
            "generated_at": _iso_now(),
            "account_id": identity.account_id,
        })
    finally:
        c.close()
