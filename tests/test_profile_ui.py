import os
import tempfile


def test_profile_form_parsing_and_persistence(monkeypatch):
    from profile_ui import profile_payload_from_form, save_profile_from_form
    from company_profile import load_profile

    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "profile.json")
        monkeypatch.setenv("OBRASIGNAL_PROFILE", path)
        form = {
            "name": "Empresa Demo",
            "activity": "estruturas metálicas",
            "countries": "PRT, ESP",
            "regions": "Leiria, Coimbra",
            "radius": "120",
            "services": "fabrico, montagem",
            "capabilities": "aço, serralharia",
            "scales": "medium, large",
            "certifications": "ISO 9001",
            "cpvs": "45, 44",
            "min_value": "100000",
            "max_value": "1000000",
            "economic_min_score": "65",
            "min_deadline_days": "15",
            "max_deadline_days": "90",
            "preferred": "open",
            "excluded": "negotiated",
            "excluded_keywords": "consultoria, fiscalização",
            "hard_exclusions": "serviço puramente intelectual",
        }
        parsed = profile_payload_from_form(form)
        assert parsed["countries"] == ["PRT", "ESP"]
        assert parsed["geographic_radius_km"] == 120.0
        assert parsed["min_value"] == 100000.0
        saved = save_profile_from_form(form)
        assert saved["regions"] == ["Leiria", "Coimbra"]
        assert saved["capability_tags"] == ["aço", "serralharia"]
        assert saved["economic_min_score"] == 65
        assert load_profile()["preferred_procedure_types"] == ["open"]


def test_profile_page_renders_open_visual_language():
    from profile_web import render_profile_page

    html = render_profile_page({"name": "<Empresa>", "activity": "metalomecânica"})
    assert "background:var(--bg)" in html
    assert "Ensina o ObraSignal" in html
    assert "&lt;Empresa&gt;" in html
    assert "hard_exclusions" not in html
