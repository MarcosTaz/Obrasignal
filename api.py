"""Native API facade for the ObraSignal mobile clients."""
from datetime import datetime, timezone
import os
from urllib.parse import urlsplit, urlunsplit
from flask import Blueprint, jsonify, request
from jwt import InvalidTokenError

import preload as _preload
from preload import APP, _deadline_dt
from auth_context import configured_identity
from auth_context_jwt import JwksUnavailableError
from company_profile import load_profile, save_profile, derive_profile
from source_registry import SOURCES
from account_registry import ensure_account
from opportunity_workflow import get_workflow, set_workflow, workflow_counts
from opportunity_lifecycle import actionable_predicate, ensure_lifecycle_table
from account_onboarding import bootstrap_account

bp = Blueprint("mobile_api", __name__, url_prefix="/api/v1")


class CompanyMembershipUnavailable(Exception):
    """Staging membership backend cannot establish tenant authorization."""


@APP.errorhandler(JwksUnavailableError)
def _jwks_unavailable(_error):
    return jsonify({"error": "authentication_service_unavailable"}), 503


@APP.errorhandler(CompanyMembershipUnavailable)
def _membership_unavailable(_error):
    return jsonify({"error": "company_authorization_unavailable"}), 503


def _db():
    return _preload._app.db()


def _iso_now():
    return datetime.now(timezone.utc).isoformat()


def _identity():
    identity = configured_identity()
    company_auth_mode = os.getenv("OBRASIGNAL_NEON_COMPANY_AUTH", "").strip()
    if company_auth_mode not in {"", "staging"}:
        # A misspelled staging flag must never silently disable the company gate.
        raise RuntimeError("Invalid OBRASIGNAL_NEON_COMPANY_AUTH")
    if not company_auth_mode:
        return identity
    # Staged Neon requires a verified provider token, never development identity.
    if (os.getenv("OBRASIGNAL_AUTH_MODE") or "development").strip().lower() != "provider":
        raise RuntimeError("Neon company authorization requires provider authentication")
    # Staging-only: the verified JWT identity alone is never a tenant grant.
    # No fallback to the user's subject or an untrusted account-id header.
    from auth_context import RequestIdentity
    from neon_company_access import authorize_company, lookup_neon_membership, CompanyAccessDenied
    from uuid import UUID
    if not identity.authenticated or not isinstance(identity.claims, dict):
        raise InvalidTokenError("neon_company_auth_requires_verified_identity")
    issuer = identity.claims.get("iss")
    subject = identity.subject
    company = request.headers.get("X-ObraSignal-Company-ID", "")
    trusted_issuer = os.getenv("OBRASIGNAL_NEON_STAGING_ISSUER", "")
    if not trusted_issuer or issuer != trusted_issuer:
        raise InvalidTokenError("neon_staging_issuer_mismatch")
    try:
        company = str(UUID(company))
        subject = str(UUID(subject))
    except (ValueError, TypeError, AttributeError):
        raise InvalidTokenError("neon_company_identifier_invalid")
    database_url = os.getenv("OBRASIGNAL_NEON_STAGING_DATABASE_URL", "")
    if not database_url:
        raise RuntimeError("Neon staging company database is not configured")
    import psycopg
    try:
        with psycopg.connect(database_url, connect_timeout=5) as connection:
            try:
                authorized = authorize_company(
                    issuer, subject, company,
                    lambda i, s, c: lookup_neon_membership(connection, i, s, c),
                )
            except CompanyAccessDenied as exc:
                raise InvalidTokenError("company_membership_denied") from exc
    except psycopg.Error as exc:
        # Never use the legacy subject/account fallback when Neon is unavailable.
        # Do not expose provider connection details in HTTP responses.
        raise CompanyMembershipUnavailable() from exc
    return RequestIdentity(
        account_id=authorized, authenticated=True,
        subject=identity.subject, claims=identity.claims,
    )


def _bounded_query_int(name, default, minimum, maximum, *, optional=False):
    raw = request.args.get(name)
    if raw in (None, ""):
        return None if optional else default
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(name) from exc
    if value < minimum or value > maximum:
        raise ValueError(name)
    return value


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
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-ObraSignal-Version, X-ObraSignal-Company-ID, Authorization"
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
    try:
        identity = _identity()
    except InvalidTokenError:
        return jsonify({"error": "authentication_required"}), 401
    except RuntimeError:
        # Configuration faults are service failures, never bad user credentials.
        # Avoid leaking issuer, token, database or environment configuration.
        return jsonify({"error": "authentication_configuration_unavailable"}), 503
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
    raw = str(value or "").strip()
    if len(raw) == 10:
        try:
            deadline_date = datetime.strptime(raw, "%Y-%m-%d").date()
        except ValueError:
            pass
        else:
            days = (deadline_date - datetime.now(timezone.utc).date()).days
            if days < 0:
                return {"state": "closed", "label": "Terminado", "days_remaining": days}
            if days == 0:
                return {"state": "unknown", "label": "Prazo hoje — hora não indicada", "days_remaining": 0}
            if days <= 2:
                return {"state": "urgent", "label": "Urgente", "days_remaining": days}
            if days <= 7:
                return {"state": "urgent", "label": "Prazo curto", "days_remaining": days}
            return {"state": "open", "label": "Aberto", "days_remaining": days}

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
    lifecycle_value = d.get("is_actionable")
    d["deadline_status"] = _deadline_state(d.get("deadline"))
    if lifecycle_value is None:
        d["is_actionable"] = d["deadline_status"]["state"] != "closed"
    else:
        d["is_actionable"] = bool(lifecycle_value)
    d["is_open"] = d["is_actionable"] and d["deadline_status"]["state"] in ("open", "urgent")
    if decision:
        d["account_decision"] = decision.get("decision")
        d["account_reason"] = decision.get("reason")
        d["account_score"] = decision.get("score")
        d["account_rule_version"] = decision.get("rule_version")
        d["account_decided_at"] = decision.get("decided_at")
        d["explanation"] = decision.get("features", {}).get("explanation")
        d["economic_fit"] = decision.get("features", {}).get("economic_fit")
        d["capability_evidence"] = decision.get("features", {}).get("capability_evidence")
        d["cpv_evidence"] = decision.get("features", {}).get("cpv_evidence")
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


@bp.route("/sources", methods=["GET"])
def sources():
    identity = request.obrasignal_identity
    items = [{"name": name, **meta} for name, meta in sorted(SOURCES.items(), key=lambda pair: (pair[1].get("priority", 99), pair[0]))]
    return jsonify({"items": items, "count": len(items), "generated_at": _iso_now(), "account_id": identity.account_id})


_PROFILE_FIELDS = {"name", "activity", "contract_interests", "coverage_mode", "keywords", "countries", "cpv_prefixes", "min_value", "max_value", "economic_min_score", "min_deadline_days", "max_deadline_days", "preferred_procedure_types", "excluded_procedure_types", "exclude_keywords", "regions", "geographic_radius_km", "services", "capability_tags", "project_scales", "certifications", "hard_exclusions"}


def _same_public_list(left, right):
    return [str(v).strip() for v in (left or []) if str(v).strip()] == [str(v).strip() for v in (right or []) if str(v).strip()]


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

    # Public flattened fields are editable in the customer UI, while the profile
    # model now tracks manual and inferred provenance separately. Only promote a
    # flattened list to manual provenance when the customer actually changed it;
    # an unchanged form round-trip must not cement old inferred values forever.
    if "cpv_prefixes" in payload and not _same_public_list(payload.get("cpv_prefixes"), current.get("cpv_prefixes")):
        merged["manual_cpv_prefixes"] = list(payload.get("cpv_prefixes") or [])
        merged["inferred_cpv_prefixes"] = []
    if "keywords" in payload and not _same_public_list(payload.get("keywords"), current.get("keywords")):
        merged["manual_keywords"] = list(payload.get("keywords") or [])
        merged["inferred_keywords"] = []

    normalized = derive_profile(str(merged.get("activity") or ""), merged)
    normalized["account_id"] = identity.account_id
    try:
        saved = save_profile(normalized, account_id=identity.account_id)
    except ValueError as exc:
        detail = exc.args[0] if exc.args else {"code": "INVALID_COMPANY_PROFILE"}
        return jsonify({"error": "invalid_profile", "detail": detail}), 400
    recalculated = bootstrap_account(identity.account_id)
    return jsonify({"ok": True, "profile": saved, "radar_recalculated": recalculated, "account_id": identity.account_id, "authenticated": identity.authenticated, "generated_at": _iso_now()})


@bp.route("/alerts", methods=["GET"])
def alerts():
    identity = request.obrasignal_identity
    limit = max(1, min(50, int(request.args.get("limit", 20) or 20)))
    unread_only = request.args.get("unread", "0").lower() in ("1", "true", "yes")
    c = _db()
    ensure_lifecycle_table(c)
    where = f"WHERE e.account_id=? AND e.event_type='new_high_match' AND {actionable_predicate('lc', 't')}"
    params = [identity.account_id]
    if unread_only:
        where += " AND e.delivered_at IS NULL"
    params.append(limit)
    rows = c.execute(f"""SELECT e.id AS event_id, e.event_key, e.score, e.created_at, e.delivered_at,
                   t.id, t.title, t.country, t.source, t.url, t.deadline, t.profile_reason, t.profile_score, t.external_id
            FROM opportunity_events e LEFT JOIN tenders t ON t.id=e.tender_id
            LEFT JOIN opportunity_lifecycle lc ON lc.source=t.source AND lc.external_id=t.external_id
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
    ensure_lifecycle_table(c)
    latest = """JOIN (
        SELECT od.source, od.external_id, MAX(od.id) AS max_id
        FROM opportunity_decisions od
        WHERE od.account_id=?
        GROUP BY od.source, od.external_id
    ) latest ON latest.max_id=d.id"""
    base = f"""FROM tenders t
        JOIN opportunity_decisions d ON d.source=t.source AND d.external_id=t.external_id
        {latest}
        LEFT JOIN opportunity_lifecycle lc ON lc.source=t.source AND lc.external_id=t.external_id
        WHERE d.account_id=? AND {actionable_predicate('lc', 't')}"""
    params = [identity.account_id, identity.account_id]
    total = c.execute(f"SELECT COUNT(*) {base}", params).fetchone()[0]
    relevant60 = c.execute(f"SELECT COUNT(*) {base} AND d.score >= 60", params).fetchone()[0]
    high = c.execute(f"SELECT COUNT(*) {base} AND d.score >= 75", params).fetchone()[0]
    very_high = c.execute(f"SELECT COUNT(*) {base} AND d.score >= 90", params).fetchone()[0]
    confirmed_open = """t.deadline IS NOT NULL AND TRIM(t.deadline)<>'' AND (
        (LENGTH(TRIM(t.deadline))=10 AND date(t.deadline)>=date('now')) OR
        (LENGTH(TRIM(t.deadline))<>10 AND datetime(t.deadline)>=datetime('now'))
    )"""
    open_count = c.execute(f"SELECT COUNT(*) {base} AND ({confirmed_open})", params).fetchone()[0]
    source_time = "COALESCE(NULLIF(t.publication_date,''), NULLIF(t.published_at,''), t.first_seen)"
    new24 = c.execute(
        f"SELECT COUNT(*) {base} AND julianday({source_time})>=julianday('now','-1 day') "
        f"AND julianday({source_time})<=julianday('now','+5 minutes')",
        params,
    ).fetchone()[0]
    last = c.execute("SELECT finished_at FROM sync_runs ORDER BY id DESC LIMIT 1").fetchone()
    c.close()
    return jsonify({
        "total": total,
        "relevant60": relevant60,
        "high": high,
        "very_high": very_high,
        "open": open_count,
        "new24": new24,
        "last_sync": last[0] if last else None,
        "account_id": identity.account_id,
    })


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
    try:
        limit = _bounded_query_int("limit", 20, 1, 100)
        offset = _bounded_query_int("offset", 0, 0, 100000)
        minscore = _bounded_query_int("minscore", None, 0, 100, optional=True)
    except ValueError as exc:
        return jsonify({"error": "invalid_query", "message": f"Parâmetro inválido: {exc.args[0]}"}), 400
    market = (request.args.get("market") or "").upper().strip()
    country = (request.args.get("country") or "").upper().strip()
    q = (request.args.get("q") or "").strip().lower()
    source = (request.args.get("source") or "").strip().upper()
    open_only = request.args.get("open", "0").lower() in ("1", "true", "yes")
    c = _db()
    ensure_lifecycle_table(c)
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
        # Match the same precision-aware definition used by /stats. A deadline
        # containing only a date stays open for that entire calendar day instead
        # of being converted to midnight and disappearing after 00:00 UTC.
        where.append("""t.deadline IS NOT NULL AND TRIM(t.deadline)<>'' AND (
            (LENGTH(TRIM(t.deadline))=10 AND date(t.deadline)>=date('now')) OR
            (LENGTH(TRIM(t.deadline))<>10 AND datetime(t.deadline)>=datetime('now'))
        )""")
    if minscore is not None:
        where.append("COALESCE(d.score,t.score)>=?")
        params.append(minscore)
    fetched = c.execute(
        f"""SELECT t.*, {actionable_predicate('lc', 't')} AS is_actionable,
                   lc.lifecycle_status, lc.lifecycle_reason,
                   lc.source_updated_at AS lifecycle_source_updated_at,
                   lc.last_observed AS lifecycle_last_observed
            FROM opportunity_decisions d
            JOIN (SELECT source, external_id, MAX(id) max_id
                  FROM opportunity_decisions WHERE account_id=? GROUP BY source, external_id) latest
              ON latest.max_id=d.id
            JOIN tenders t ON t.source=d.source AND t.external_id=d.external_id
            LEFT JOIN opportunity_lifecycle lc ON lc.source=t.source AND lc.external_id=t.external_id
            WHERE d.account_id=? AND {' AND '.join(where)}
            ORDER BY COALESCE(d.score,t.score) DESC, t.deadline ASC, t.id ASC
            LIMIT ? OFFSET ?""",
        (identity.account_id, identity.account_id, *params, limit + 1, offset),
    ).fetchall()
    has_more = len(fetched) > limit
    rows = fetched[:limit]
    decisions = _latest_decisions(c, identity.account_id, [r["external_id"] for r in rows])
    items = [_row(r, decisions.get((r["source"], r["external_id"])), get_workflow(c, identity.account_id, r["source"], r["external_id"])) for r in rows]
    c.close()
    page = {"limit": limit, "offset": offset, "has_more": has_more, "next_offset": offset + limit if has_more else None}
    return jsonify({"items": items, "count": len(items), "page": page, "market": market, "generated_at": _iso_now(), "account_id": identity.account_id})


@bp.route("/opportunities/<int:opportunity_id>", methods=["GET"])
def opportunity_detail(opportunity_id):
    identity = request.obrasignal_identity
    c = _db()
    try:
        ensure_lifecycle_table(c)
        row = c.execute(
            f"""SELECT t.*, {actionable_predicate('lc', 't')} AS is_actionable,
                      lc.lifecycle_status, lc.lifecycle_reason,
                      lc.source_updated_at AS lifecycle_source_updated_at,
                      lc.last_observed AS lifecycle_last_observed
               FROM tenders t
               LEFT JOIN opportunity_lifecycle lc
                 ON lc.source=t.source AND lc.external_id=t.external_id
               WHERE t.id=?""",
            (opportunity_id,),
        ).fetchone()
        if row is None:
            return jsonify({"error": "not_found"}), 404
        decisions = _latest_decisions(c, identity.account_id, [row["external_id"]])
        decision = decisions.get((row["source"], row["external_id"]))
        workflow = get_workflow(c, identity.account_id, row["source"], row["external_id"])
        return jsonify(_row(row, decision, workflow))
    finally:
        c.close()


@bp.route("/opportunities/<int:opportunity_id>/workflow", methods=["GET", "POST"])
def opportunity_workflow(opportunity_id):
    identity = request.obrasignal_identity
    payload = request.get_json(silent=True) or {}
    c = _db()
    try:
        row = c.execute("SELECT source, external_id FROM tenders WHERE id=?", (opportunity_id,)).fetchone()
        if row is None:
            return jsonify({"error": "not_found"}), 404
        if request.method == "GET":
            workflow = get_workflow(c, identity.account_id, row["source"], row["external_id"])
            return jsonify({"workflow": workflow, "account_id": identity.account_id, "generated_at": _iso_now()})
        workflow = set_workflow(
            c,
            identity.account_id,
            row["source"],
            row["external_id"],
            payload.get("status"),
            payload.get("note"),
        )
        return jsonify({"ok": True, "workflow": workflow, "account_id": identity.account_id, "generated_at": _iso_now()})
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    finally:
        c.close()


if "mobile_api" not in APP.blueprints:
    APP.register_blueprint(bp)