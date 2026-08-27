from __future__ import annotations

import hmac
import os
import secrets
from functools import wraps

from flask import Flask, jsonify, redirect, render_template, request, session, url_for

from .actions import execute, list_actions
from .business_api import business_api
from .ranking import highest_value_actions, rank_portfolio
from .registry import append_audit, get_company, ingest_factory_state, init_db, list_audit, list_companies, list_company_history, register_company_stub
from .security import safe_local_redirect_target


def create_app(test_config: dict | None = None) -> Flask:
    session_secret = os.getenv("FCC_SESSION_SECRET")
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config.update(
        SECRET_KEY=session_secret or os.urandom(32).hex(),
        FCC_SESSION_SECRET_CONFIGURED=bool(session_secret),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Strict",
        SESSION_COOKIE_SECURE=os.getenv("FCC_SECURE_COOKIE", "1") == "1",
        MAX_CONTENT_LENGTH=128 * 1024,
    )
    if test_config:
        app.config.update(test_config)
    init_db()
    app.register_blueprint(business_api)

    @app.after_request
    def security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        response.headers.setdefault("Content-Security-Policy", "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; img-src 'self' data:; object-src 'none'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'")
        response.headers.setdefault("Cache-Control", "no-store")
        if app.config.get("SESSION_COOKIE_SECURE"):
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return response

    def is_authenticated() -> bool:
        if app.config.get("TESTING") and app.config.get("BYPASS_AUTH"):
            return True
        return bool(session.get("fcc_auth"))

    def auth_required(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            if not is_authenticated():
                if request.path.startswith("/api/"):
                    return jsonify({"ok": False, "error": "authentication_required"}), 401
                return redirect(url_for("login", next=request.path))
            return fn(*args, **kwargs)
        return wrapped

    def csrf_required(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            if app.config.get("TESTING") and app.config.get("BYPASS_AUTH"):
                return fn(*args, **kwargs)
            expected = session.get("csrf_token")
            candidate = request.headers.get("X-CSRF-Token") or request.form.get("csrf_token", "")
            if not expected or not candidate or not hmac.compare_digest(str(candidate), str(expected)):
                if request.path.startswith("/api/"):
                    return jsonify({"ok": False, "error": "csrf_validation_failed"}), 403
                return "CSRF validation failed", 403
            return fn(*args, **kwargs)
        return wrapped

    def factory_ingest_required(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            expected = os.getenv("FCC_FACTORY_INGEST_TOKEN")
            if not expected:
                return jsonify({"ok": False, "error": "factory_ingest_not_configured"}), 503
            header = request.headers.get("Authorization", "")
            prefix = "Bearer "
            candidate = header[len(prefix):] if header.startswith(prefix) else ""
            if not candidate or not hmac.compare_digest(candidate, expected):
                return jsonify({"ok": False, "error": "factory_ingest_authentication_required"}), 401
            return fn(*args, **kwargs)
        return wrapped

    def company_or_404(company_id: str):
        company = get_company(company_id)
        if company:
            return company, None
        return None, (jsonify({"error": "not_found", "company_id": company_id}), 404)

    @app.get("/health")
    def health():
        return jsonify({"status": "ok", "truth": "process_alive_not_global_green"})

    @app.route("/login", methods=["GET", "POST"])
    def login():
        admin_token = os.getenv("FCC_ADMIN_TOKEN")
        session_configured = bool(app.config.get("FCC_SESSION_SECRET_CONFIGURED"))
        error = None
        if request.method == "POST":
            candidate = request.form.get("token", "")
            if not admin_token:
                error = "FCC_ADMIN_TOKEN is not configured. Access fails closed."
            elif not session_configured and not app.config.get("TESTING"):
                error = "FCC_SESSION_SECRET is not configured. Access fails closed."
            elif hmac.compare_digest(candidate, admin_token):
                session.clear()
                session["fcc_auth"] = True
                session["csrf_token"] = secrets.token_urlsafe(32)
                target = safe_local_redirect_target(request.args.get("next"), url_for("dashboard"))
                return redirect(target)
            else:
                error = "Invalid access token."
        return render_template("login.html", error=error, configured=bool(admin_token), session_configured=session_configured)

    @app.post("/logout")
    @auth_required
    @csrf_required
    def logout():
        session.clear()
        return redirect(url_for("login"))

    @app.get("/")
    @auth_required
    def dashboard():
        companies = list_companies(); ranks = rank_portfolio(companies); by_id = {c.id: c for c in companies}
        ranked = [{"rank": r, "company": by_id[r.company_id]} for r in ranks]
        return render_template("dashboard.html", companies=companies, ranked=ranked, actions=list_actions(), portfolio_actions=highest_value_actions(companies), audit=list_audit(12), csrf_token=session.get("csrf_token", ""))

    @app.get("/company/<company_id>")
    @auth_required
    def company_page(company_id: str):
        company = get_company(company_id)
        if not company:
            return "Not found", 404
        ranking = rank_portfolio([company])[0]
        return render_template("company.html", company=company, ranking=ranking, actions=list_actions(), history=list_company_history(company_id, 12), csrf_token=session.get("csrf_token", ""))

    @app.get("/api/companies")
    @auth_required
    def api_companies():
        companies = list_companies(); ranks = {r.company_id: r.to_dict() for r in rank_portfolio(companies)}
        return jsonify({"companies": [c.to_dict() for c in companies], "ranking": ranks})

    @app.post("/api/companies/register")
    @auth_required
    @csrf_required
    def api_register_company():
        data = request.get_json(silent=True) or {}
        try:
            company = register_company_stub(
                company_id=str(data.get("id", "")), name=str(data.get("name", "")), mission=str(data.get("mission", "")),
                kind=str(data.get("kind", "company")), repository_full_name=data.get("repository"), application_url=data.get("application_url"),
            )
        except ValueError as exc:
            return jsonify({"ok": False, "error": "invalid_company_manifest", "detail": str(exc)}), 400
        return jsonify({"ok": True, "company": company.to_dict()}), 201

    @app.post("/api/ingest/factory-state")
    @factory_ingest_required
    def api_ingest_factory_state():
        data = request.get_json(silent=True) or {}
        try:
            company = ingest_factory_state(
                company_id=str(data.get("company_id", "")), factory_name=str(data.get("factory_name", "")),
                active=str(data.get("active", "")), next_value=str(data.get("next", "")), wait=str(data.get("wait", "")),
                source=str(data.get("source", "")), observed_at=data.get("observed_at"), freshness_seconds=data.get("freshness_seconds", 3600),
                material_delta=data.get("material_delta"),
            )
        except (TypeError, ValueError) as exc:
            append_audit(
                actor="factory_ingest",
                action="ingest_factory_state",
                level="GREEN",
                company_id=str(data.get("company_id", ""))[:120] or None,
                result="rejected_invalid_factory_state",
                source_data={"factory_name": str(data.get("factory_name", ""))[:160], "source": str(data.get("source", ""))[:300], "payload_keys": sorted(str(key)[:120] for key in data.keys())[:50]},
                failure_state=str(exc)[:300],
            )
            return jsonify({"ok": False, "error": "invalid_factory_state", "detail": str(exc)}), 400
        factory_name = str(data.get("factory_name", "")).strip()
        factory = next((item for item in company.to_dict()["factories"] if item["name"] == factory_name), None)
        return jsonify({"ok": True, "company_id": company.id, "factory": factory, "last_update": company.last_update}), 200

    @app.get("/api/companies/<company_id>")
    @auth_required
    def api_company(company_id: str):
        company, error = company_or_404(company_id)
        return error or jsonify(company.to_dict())

    @app.get("/api/companies/<company_id>/metrics")
    @auth_required
    def api_company_metrics(company_id: str):
        company, error = company_or_404(company_id)
        if error: return error
        payload = company.to_dict()
        return jsonify({"company_id": company_id, "revenue": payload["revenue"], "pipeline": payload["pipeline"], "customers": payload["customers"], "metrics": payload["metrics"], "data_freshness": payload["data_freshness"]})

    @app.get("/api/companies/<company_id>/factory-state")
    @auth_required
    def api_company_factory_state(company_id: str):
        company, error = company_or_404(company_id)
        if error: return error
        return jsonify({"company_id": company_id, "ACTIVE": company.active, "NEXT": company.next, "WAIT": company.wait, "factories": company.to_dict()["factories"], "last_update": company.last_update})

    @app.get("/api/companies/<company_id>/history")
    @auth_required
    def api_company_history(company_id: str):
        company, error = company_or_404(company_id)
        if error: return error
        try:
            limit = int(request.args.get("limit", "50"))
        except ValueError:
            return jsonify({"ok": False, "error": "invalid_history_limit"}), 400
        return jsonify({"company_id": company.id, "history": list_company_history(company_id, limit)})

    @app.get("/api/companies/<company_id>/risks")
    @auth_required
    def api_company_risks(company_id: str):
        company, error = company_or_404(company_id)
        if error: return error
        return jsonify({"company_id": company_id, "risks": company.to_dict()["risks"], "data_freshness": company.data_freshness.value})

    @app.get("/api/companies/<company_id>/revenue")
    @auth_required
    def api_company_revenue(company_id: str):
        company, error = company_or_404(company_id)
        if error: return error
        return jsonify({"company_id": company_id, "revenue": company.to_dict()["revenue"]})

    @app.get("/api/companies/<company_id>/actions")
    @auth_required
    def api_company_actions(company_id: str):
        _, error = company_or_404(company_id)
        if error: return error
        return jsonify({"company_id": company_id, "actions": list_actions()})

    @app.get("/api/actions")
    @auth_required
    def api_actions():
        return jsonify({"actions": list_actions()})

    @app.post("/api/actions/<action_id>/execute")
    @auth_required
    @csrf_required
    def api_execute(action_id: str):
        data = request.get_json(silent=True) or {}; company_id = data.get("company_id")
        if not isinstance(company_id, str) or not company_id:
            return jsonify({"ok": False, "error": "company_id_required"}), 400
        result, status = execute(action_id, company_id, data.get("payload") or {})
        return jsonify(result), status

    @app.get("/api/audit")
    @auth_required
    def api_audit():
        return jsonify({"events": list_audit(100)})

    return app


APP = create_app()

if __name__ == "__main__":
    APP.run(host="127.0.0.1", port=int(os.getenv("PORT", "8088")), debug=False)
