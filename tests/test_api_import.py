def test_api_import_keeps_profile_endpoint():
    import api

    routes = {rule.rule for rule in api.APP.url_map.iter_rules()}
    assert "/api/v1/profile" in routes


def test_production_wsgi_registers_opportunity_detail_endpoint():
    import cors_app

    routes = {rule.rule for rule in cors_app.APP.url_map.iter_rules()}
    assert "/api/v1/opportunities/<int:opportunity_id>" in routes
