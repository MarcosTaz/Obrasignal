from __future__ import annotations

import hmac
import os
from functools import wraps

from flask import Flask, jsonify, redirect, render_template, request, session, url_for

from .actions import execute, list_actions
from .ranking import highest_value_actions, rank_portfolio
from .registry import get_company, init_db, list_audit, list_companies


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

    @app.get("/api/companies/<company_id>")
    @auth_required
    def api_company(company_id: str):
        company = get_company(company_id)
        return jsonify(company.to_dict()) if company else (jsonify({"error": "not_found"}), 404)

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
