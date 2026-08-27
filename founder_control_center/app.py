from __future__ import annotations

import hmac
import os
from functools import wraps

from flask import Flask, jsonify, redirect, render_template, request, session, url_for

from .actions import execute, list_actions
from .ranking import highest_value_actions, rank_portfolio
from .registry import get_company, init_db, list_audit, list_companies, register_company_stub


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config.update(SECRET_KEY=os.getenv("FCC_SESSION_SECRET", os.urandom(32).hex()), SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Strict", SESSION_COOKIE_SECURE=os.getenv("FCC_SECURE_COOKIE", "1") == "1", MAX_CONTENT_LENGTH=128 * 1024)
    if test_config:
        app.config.update(test_config)
    init_db()

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
        configured = os.getenv("FCC_ADMIN_TOKEN")
        error = None
        if request.method == "POST":
            candidate = request.form.get("token", "")
            if not configured:
                error = "FCC_ADMIN_TOKEN is not configured. Access fails closed."
            elif hmac.compare_digest(candidate, configured):
                session["fcc_auth"] = True
                return redirect(request.args.get("next") or url_for("dashboard"))
            else:
                error = "Invalid access token."
        return render_template("login.html", error=error, configured=bool(configured))

    @app.post("/logout")
    def logout():
        session.clear()
        return redirect(url_for("login"))

    @app.get("/")
    @auth_required
    def dashboard():
        companies = list_companies(); ranks = rank_portfolio(companies); by_id = {c.id: c for c in companies}
        ranked = [{"rank": r, "company": by_id[r.company_id]} for r in ranks]
        return render_template("dashboard.html", companies=companies, ranked=ranked, actions=list_actions(), portfolio_actions=highest_value_actions(companies), audit=list_audit(12))

    @app.get("/company/<company_id>")
    @auth_required
    def company_page(company_id: str):
        company = get_company(company_id)
        if not company:
            return "Not found", 404
        ranking = rank_portfolio([company])[0]
        return render_template("company.html", company=company, ranking=ranking, actions=list_actions())

    @app.get("/api/companies")
    @auth_required
    def api_companies():
        companies = list_companies(); ranks = {r.company_id: r.to_dict() for r in rank_portfolio(companies)}
        return jsonify({"companies": [c.to_dict() for c in companies], "ranking": ranks})

    @app.post("/api/companies/register")
    @auth_required
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
