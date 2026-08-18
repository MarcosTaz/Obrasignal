from profile_web import render_profile_page
from profile_ui import profile_payload_from_form, save_profile_from_form


def register_profile_page(app):
    @app.route("/profile", methods=["GET", "POST"])
    def profile_page():
        from company_profile import load_profile
        if app.request.method == "POST":
            saved = save_profile_from_form(app.request.form)
            return app.redirect("/profile")
        return render_profile_page(load_profile())
