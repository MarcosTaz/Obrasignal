from visual_system import TOKENS, render_status_pill, status_class, visual_css


def test_visual_system_uses_open_light_palette():
    assert TOKENS["bg"] == "#F5F8FC"
    assert TOKENS["surface"] == "#FFFFFF"
    assert TOKENS["accent"] == "#2166F3"
    css = visual_css()
    assert "--os-bg" in css
    assert "#FFFFFF" in css


def test_status_classes_map_to_business_states():
    assert status_class("QUALIFIED") == "os-pill--hot"
    assert status_class("REVIEW") == "os-pill--review"
    assert status_class("REJECTED") == "os-pill--reject"
    assert status_class("SEM DECISÃO") == ""


def test_status_pill_escapes_dynamic_status():
    html = render_status_pill('<script>alert(1)</script>')
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "<script>alert(1)</script>" not in html
