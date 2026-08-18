from flask import redirect, request

from profile_ui import save_profile_from_form
from profile_web import render_profile_page
from company_profile import load_profile


__all__ = ["render_profile_page", "register_profile_page"]


def register_profile_page(app):
    """Register the legacy-compatible profile web route on the given Flask app."""
    endpoint = "company_profile_page"
    if endpoint in app.view_functions:
        return

    @app.route("/profile", methods=["GET", "POST"], endpoint=endpoint)
    def company_profile_page():
        if request.method == "POST":
            save_profile_from_form(request.form)
            return redirect("/profile", code=303)
        return render_profile_page(load_profile())
