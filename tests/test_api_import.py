def test_api_import_keeps_profile_endpoint():
    import api

    routes = {rule.rule for rule in api.APP.url_map.iter_rules()}
    assert "/api/v1/profile" in routes
