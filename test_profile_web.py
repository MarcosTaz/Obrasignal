from profile_web import render_profile_page


def test_profile_page_renders_open_future_layout():
    html = render_profile_page({
        "name": "Empresa X",
        "activity": "metalomecânica",
        "countries": ["PRT"],
        "regions": ["Leiria"],
        "geographic_radius_km": 80,
        "services": ["estruturas metálicas"],
        "min_value": 100000,
        "economic_min_score": 65,
    })

    assert "Ensina o sistema a conhecer a tua empresa." in html
    assert "Economic Fit mínimo" in html
    assert "estruturas metálicas" in html
    assert "background:linear-gradient" in html


def test_profile_page_does_not_render_raw_html_from_profile_values():
    html = render_profile_page({
        "name": '<script>alert(1)</script>',
        "activity": '<img src=x onerror=alert(1)>',
    })

    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "&lt;img src=x onerror=alert(1)&gt;" in html
