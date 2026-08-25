"""HTTP boundary for the pursuit workspace capability.

Importing this module registers an additive blueprint on the shared Flask app.
Authentication and tenant identity reuse the existing auth context; account_id is
never accepted from request payloads.
"""
from flask import Blueprint, jsonify, request
from jwt import InvalidTokenError

import preload as _preload
from auth_context import configured_identity
from pursuit_workspace import (
    EMPTY_PROVIDERS,
    add_blocker,
    add_note,
    add_question,
    create_workspace,
    ensure_workspace_tables,
    get_workspace,
    resolve_blocker,
    update_workspace,
    workspace_view,
)

bp = Blueprint("pursuit_workspace_api", __name__, url_prefix="/api/v1/opportunities")
PROVIDERS = EMPTY_PROVIDERS


def _db():
    return _preload._app.db()


def _identity():
    identity = getattr(request, "obrasignal_identity", None)
    return identity or configured_identity()


def _subject(identity):
    return getattr(identity, "subject", None)


@bp.before_request
def _require_identity():
    if request.method == "OPTIONS":
        return None
    try:
        request.obrasignal_identity = _identity()
    except (RuntimeError, InvalidTokenError):
        return jsonify({"error": "authentication_required"}), 401
    return None


def _error(exc):
    code = str(exc)
    if isinstance(exc, PermissionError):
        return jsonify({"error": code}), 403
    if isinstance(exc, LookupError):
        return jsonify({"error": code}), 404
    if isinstance(exc, ValueError):
        return jsonify({"error": code}), 400
    raise exc


@bp.route("/<int:opportunity_id>/workspace", methods=["POST", "GET", "PATCH"])
def workspace(opportunity_id):
    identity = request.obrasignal_identity
    conn = _db()
    try:
        ensure_workspace_tables(conn)
        if request.method == "POST":
            item = create_workspace(conn, identity.account_id, opportunity_id)
            return jsonify({"workspace": item, "account_id": identity.account_id}), 201
        if request.method == "GET":
            return jsonify(workspace_view(conn, identity.account_id, opportunity_id, providers=PROVIDERS))
        payload = request.get_json(silent=True) or {}
        item = update_workspace(
            conn, identity.account_id, opportunity_id, payload,
            actor_subject=_subject(identity),
        )
        return jsonify({"workspace": item, "account_id": identity.account_id})
    except (LookupError, ValueError, PermissionError) as exc:
        return _error(exc)
    finally:
        conn.close()


@bp.route("/<int:opportunity_id>/workspace/blockers", methods=["POST"])
def blockers(opportunity_id):
    identity = request.obrasignal_identity
    payload = request.get_json(silent=True) or {}
    conn = _db()
    try:
        item = add_blocker(
            conn, identity.account_id, opportunity_id, payload.get("title"),
            severity=payload.get("severity"), actor_subject=_subject(identity),
        )
        return jsonify({"blocker": item}), 201
    except (LookupError, ValueError, PermissionError) as exc:
        return _error(exc)
    finally:
        conn.close()


@bp.route("/<int:opportunity_id>/workspace/blockers/<int:blocker_id>/resolve", methods=["POST"])
def blocker_resolve(opportunity_id, blocker_id):
    identity = request.obrasignal_identity
    conn = _db()
    try:
        return jsonify({"blocker": resolve_blocker(conn, identity.account_id, opportunity_id, blocker_id)})
    except (LookupError, ValueError, PermissionError) as exc:
        return _error(exc)
    finally:
        conn.close()


@bp.route("/<int:opportunity_id>/workspace/notes", methods=["POST"])
def notes(opportunity_id):
    identity = request.obrasignal_identity
    payload = request.get_json(silent=True) or {}
    conn = _db()
    try:
        item = add_note(conn, identity.account_id, opportunity_id, payload.get("body"), actor_subject=_subject(identity))
        return jsonify({"note": item}), 201
    except (LookupError, ValueError, PermissionError) as exc:
        return _error(exc)
    finally:
        conn.close()


@bp.route("/<int:opportunity_id>/workspace/questions", methods=["POST"])
def questions(opportunity_id):
    identity = request.obrasignal_identity
    payload = request.get_json(silent=True) or {}
    conn = _db()
    try:
        item = add_question(
            conn, identity.account_id, opportunity_id, payload.get("question"),
            source_ref=payload.get("source_ref"), owner_id=payload.get("owner_id"),
            actor_subject=_subject(identity),
        )
        return jsonify({"question": item}), 201
    except (LookupError, ValueError, PermissionError) as exc:
        return _error(exc)
    finally:
        conn.close()


if "pursuit_workspace_api" not in _preload.APP.blueprints:
    _preload.APP.register_blueprint(bp)
