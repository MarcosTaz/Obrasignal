from profile_ui import profile_payload_from_form, save_profile_from_form
from profile_web import render_profile_page


def test_profile_form_parsing_and_persistence(monkeypatch, tmp_path):
    profile_path = tmp_path / "profile.json"
    monkeypatch.setenv("OBRASIGNAL_PROFILE", str(profile_path))

    class Form(dict):
        def get(self, key, default=""):
            return super().get(key, default)

    form = Form(
        name="Empresa Demo",
        activity="estruturas metálicas",
        countries="PRT, ESP",
        regions="Leiria, Coimbra",
        radius="100",
        services="fabrico, montagem",
        capabilities="aço, serralharia",
        scales="medium, large",
        certifications="ISO 9001",
        cpvs="45, 44",
        min_value="100000",
        max_value="1000000",
        economic_min_score="60",
        min_deadline_days="15",
        max_deadline_days="90",
        preferred="open",
        excluded="negotiated",
        excluded_keywords="consultoria, fiscalização",
        hard_exclusions="serviço puramente intelectual",
    )

    payload = profile_payload_from_form(form)
    assert payload["countries"] == ["PRT", "ESP"]
    assert payload["min_value"] == 100000.0
    assert payload["economic_min_score"] == 60

    saved = save_profile_from_form(form)
    assert saved["regions"] == ["Leiria", "Coimbra"]
    assert saved["preferred_procedure_types"] == ["open"]
    assert saved["excluded_procedure_types"] == ["negotiated"]


def test_profile_page_renders_open_visual_language():
    html = render_profile_page({"name": "<Empresa>", "activity": "estruturas metálicas", "countries": ["PRT"]})
    assert "background:var(--bg)" in html
    assert "Ensina o ObraSignal" in html
    assert "&lt;Empresa&gt;" in html
