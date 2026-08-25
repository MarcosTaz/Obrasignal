"""HTTP adapter for Search Profiles v0.

Importing this module installs the additive search-profile blueprint and routes
the existing opportunity-search endpoint through the canonical search contract.
The production WSGI entrypoint imports this adapter explicitly.
"""
from __future__ import annotations

from flask import Blueprint, jsonify, request

import api as _api
from search_profiles import (
    SearchProfileError,
    SearchProfileNeedsUpdate,
    SearchProfileNotFound,
    create_search_profile,
    delete_search_profile,
    get_search_profile,
    list_search_profiles,
    parse_query_filters,
    query_opportunities,
    run_search_profile,
    update_search_profile,
)
from opportunity_workflow import get_workflow

bp = Blueprint("search_profiles_api", __name__, url_prefix="/api/v1")

_CREATE_FIELDS = {"name", "filters", "sort", "is_default"}
_UPDATE_FIELDS = {"name", "filters", "sort", "is_default"}


@bp.before_request
def _identity_guard():
    return _api._require_identity()


@bp.after_request
def _headers(response):
    response = _api._apply_cors(response)
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PATCH, DELETE, OPTIONS"
    return response


def _payload(allowed):
    payload = request.get_json(silent=True)
    if payload is None:
        payload = {}
    if not isinstance(payload, dict):
        raise SearchProfileError("payload must be an object")
    unknown = set(payload) - allowed
    if unknown:
        raise SearchProfileError("unsupported fields: " + ", ".join(sorted(unknown)))
    return payload


def _render_rows(conn, account_id, rows):
    decisions = _api._latest_decisions(conn, account_id, [r["external_id"] for r in rows])
    return [
        _api._row(
            row,
            decisions.get((row["source"], row["external_id"])),
            get_workflow(conn, account_id, row["source"], row["external_id"]),
        )
        for row in rows
    ]


def _search_response(identity, filters, limit, sort):
    conn = _api._db()
    try:
        rows = query_opportunities(conn, identity.account_id, filters, limit=limit, sort=sort)
        items = _render_rows(conn, identity.account_id, rows)
        return {
            "items": items,
            "count": len(items),
            "market": filters.get("market", "PT"),
            "generated_at": _api._iso_now(),
            "account_id": identity.account_id,
        }
    finally:
        conn.close()


def canonical_opportunities():
    identity = request.obrasignal_identity
    try:
        filters, limit, sort = parse_query_filters(request.args)
    except SearchProfileError as exc:
        return jsonify({"error": "invalid_search", "detail": str(exc)}), 400
    return jsonify(_search_response(identity, filters, limit, sort))


@bp.route("/search-profiles", methods=["GET", "POST"])
def search_profiles_collection():
    identity = request.obrasignal_identity
    conn = _api._db()
    try:
        if request.method == "GET":
            items = list_search_profiles(conn, identity.account_id)
            return jsonify({"items": items, "count": len(items), "account_id": identity.account_id, "generated_at": _api._iso_now()})
        payload = _payload(_CREATE_FIELDS)
        profile = create_search_profile(
            conn,
            identity.account_id,
            name=payload.get("name"),
            filters=payload.get("filters"),
            sort=payload.get("sort"),
            is_default=payload.get("is_default", False),
        )
        return jsonify({"profile": profile, "account_id": identity.account_id}), 201
    except SearchProfileError as exc:
        return jsonify({"error": exc.code, "detail": str(exc)}), 400
    finally:
        conn.close()


@bp.route("/search-profiles/<profile_id>", methods=["GET", "PATCH", "DELETE"])
def search_profile_item(profile_id):
    identity = request.obrasignal_identity
    conn = _api._db()
    try:
        if request.method == "GET":
            profile = get_search_profile(conn, identity.account_id, profile_id)
            return jsonify({"profile": profile, "account_id": identity.account_id})
        if request.method == "DELETE":
            delete_search_profile(conn, identity.account_id, profile_id)
            return jsonify({"ok": True, "profile_id": profile_id})
        profile = update_search_profile(conn, identity.account_id, profile_id, _payload(_UPDATE_FIELDS))
        return jsonify({"profile": profile, "account_id": identity.account_id})
    except SearchProfileNotFound:
        # Deliberately identical for nonexistent and other-tenant IDs.
        return jsonify({"error": "not_found"}), 404
    except SearchProfileNeedsUpdate as exc:
        return jsonify({"error": exc.code, "detail": str(exc)}), 409
    except SearchProfileError as exc:
        return jsonify({"error": exc.code, "detail": str(exc)}), 400
    finally:
        conn.close()


@bp.route("/search-profiles/<profile_id>/run", methods=["POST"])
def run_profile(profile_id):
    identity = request.obrasignal_identity
    try:
        _payload(set())
        raw_limit = request.args.get("limit", 20) or 20
        limit = int(raw_limit)
        if not 1 <= limit <= 100:
            raise SearchProfileError("limit must be between 1 and 100")
    except (TypeError, ValueError, SearchProfileError) as exc:
        return jsonify({"error": "invalid_search", "detail": str(exc)}), 400

    conn = _api._db()
    try:
        profile, rows = run_search_profile(conn, identity.account_id, profile_id, limit=limit)
        items = _render_rows(conn, identity.account_id, rows)
        # Keep the existing search-result contract. Profile metadata remains
        # available through the profile endpoints instead of changing results.
        return jsonify({
            "items": items,
            "count": len(items),
            "market": profile["filters"].get("market", "PT"),
            "generated_at": _api._iso_now(),
            "account_id": identity.account_id,
        })
    except SearchProfileNotFound:
        return jsonify({"error": "not_found"}), 404
    except SearchProfileNeedsUpdate as exc:
        return jsonify({"error": exc.code, "detail": str(exc)}), 409
    except SearchProfileError as exc:
        return jsonify({"error": exc.code, "detail": str(exc)}), 400
    finally:
        conn.close()


def install(app=None):
    app = app or _api.APP
    if "search_profiles_api" not in app.blueprints:
        app.register_blueprint(bp)
    # The endpoint identity stays ``mobile_api.opportunities`` so its existing
    # authenticated before/after hooks still apply. Only the query implementation
    # is replaced, avoiding a second search route or divergent business logic.
    if "mobile_api.opportunities" in app.view_functions:
        app.view_functions["mobile_api.opportunities"] = canonical_opportunities
    return app


install()
