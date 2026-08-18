import api
import profile_page


def test_profile_page_get_and_post(monkeypatch, tmp_path):
    profile_path = tmp_path / "profile.json"
    monkeypatch.setenv("OBRASIGNAL_PROFILE", str(profile_path))

    profile_page.register_profile_page(api.APP)
    client = api.APP.test_client()

    get_response = client.get("/profile")
    assert get_response.status_code == 200
    html = get_response.get_data(as_text=True)
    assert "Ensina o ObraSignal" in html
    assert "Economic Fit" in html

    post_response = client.post("/profile", data={
        "name": "Empresa Demo",
        "activity": "estruturas metálicas",
        "countries": "PRT, ESP",
        "regions": "Leiria",
        "radius": "100",
        "services": "fabrico, montagem",
        "capabilities": "aço",
        "scales": "medium",
        "certifications": "ISO 9001",
        "cpvs": "45",
        "min_value": "100000",
        "max_value": "1000000",
        "economic_min_score": "60",
        "min_deadline_days": "15",
        "preferred": "open",
        "excluded": "negotiated",
        "excluded_keywords": "consultoria",
        "hard_exclusions": "serviço puramente intelectual",
    })
    assert post_response.status_code == 303

    stored = api.load_profile()
    assert stored["regions"] == ["Leiria"]
    assert stored["preferred_procedure_types"] == ["open"]
    assert stored["excluded_procedure_types"] == ["negotiated"]
