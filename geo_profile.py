"""Profile-aware geographic fit for procurement opportunities."""

DEFAULT_PROFILE = {
    "countries": {"PRT"},
    "nuts": set(),
    "cities": set(),
    "postal_prefixes": set(),
}


def _norm(value):
    return str(value or "").strip().upper()


def geographic_fit(item, profile=None):
    profile = profile or DEFAULT_PROFILE
    countries = {_norm(x) for x in profile.get("countries", set())}
    nuts = {_norm(x) for x in profile.get("nuts", set())}
    cities = {_norm(x) for x in profile.get("cities", set())}
    prefixes = {_norm(x) for x in profile.get("postal_prefixes", set())}

    item_country = _norm(item.get("country_code") or item.get("place_country"))
    item_nuts = {_norm(x) for x in (item.get("nuts_codes") or [])}
    item_city = _norm(item.get("city") or item.get("place_city"))
    postcode = _norm(item.get("postal_code") or item.get("place_postal_code"))

    if countries and item_country in countries:
        if nuts and item_nuts & nuts:
            return {"score": 5, "confidence": 100, "reason": "NUTS prioritário"}
        if cities and item_city in cities:
            return {"score": 5, "confidence": 100, "reason": "cidade prioritária"}
        if prefixes and any(postcode.startswith(p) for p in prefixes):
            return {"score": 5, "confidence": 100, "reason": "código postal prioritário"}
        return {"score": 3, "confidence": 80, "reason": "país compatível"}

    if item_country and countries:
        return {"score": 0, "confidence": 100, "reason": "país fora do perfil"}

    return {"score": 2, "confidence": 20, "reason": "localização insuficiente"}
