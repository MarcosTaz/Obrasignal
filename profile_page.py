from flask import redirect, request

from company_profile import load_profile
from profile_ui import save_profile_from_form
from profile_web import render_profile_page

__all__ = ["render_profile_page", "register_profile_page"]


def register_profile_page(app):
    """Register the company profile page on a Flask app exactly once."""
    endpoint = "company_profile_page"
    if endpoint in app.view_functions:
        return

    @app.route("/profile", methods=["GET", "POST"], endpoint=endpoint)
    def company_profile_page():
        if request.method == "POST":
            save_profile_from_form(request.form)
            return redirect("/profile", code=303)
        return render_profile_page(load_profile())

