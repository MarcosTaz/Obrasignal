"""Match procurement lots against a company profile.

A notice may have multiple lots and each lot may have multiple places of
performance. The matcher deliberately returns the best actionable lot rather
than collapsing the whole notice into one location.
"""


def _text(value):
    return str(value or "").strip().lower()


def _location_match(location, profile):
    if not location:
        return {"score": 2, "status": "UNKNOWN"}
    country = _text(location.get("country"))
    nuts = _text(location.get("nuts3"))
    city = _text(location.get("city"))
    postcode = _text(location.get("postcode"))

    countries = {_text(x) for x in profile.get("countries", [])}
    nuts_targets = {_text(x) for x in profile.get("nuts3", [])}
    cities = {_text(x) for x in profile.get("cities", [])}
    postcodes = {_text(x) for x in profile.get("postcodes", [])}

    if postcode and postcode in postcodes:
        return {"score": 5, "status": "MATCHED", "reason": "postcode"}
    if city and city in cities:
        return {"score": 5, "status": "MATCHED", "reason": "city"}
    if nuts and nuts in nuts_targets:
        return {"score": 5, "status": "MATCHED", "reason": "nuts3"}
    if country and country in countries:
        return {"score": 3, "status": "MATCHED", "reason": "country"}
    if location.get("broad"):
        return {"score": 2, "status": "BROAD", "reason": "broad area"}
    return {"score": 0, "status": "OUTSIDE"}


def match_lot(lot, profile):
    """Return the best geographic match and preserve all location outcomes."""
    locations = lot.get("locations") or []
    matches = [_location_match(location, profile) for location in locations]
    if not matches:
        best = {"score": 2, "status": "UNKNOWN", "reason": "no location supplied"}
    else:
        best = max(matches, key=lambda x: x["score"])
    return {
        "lot_id": lot.get("lot_id"),
        "geo_score": best["score"],
        "geo_status": best["status"],
        "geo_reason": best.get("reason"),
        "location_matches": matches,
    }


def rank_lots(lots, profile):
    """Rank lots by geographic fit, retaining the original lot data."""
    ranked = []
    for lot in lots or []:
        result = match_lot(lot, profile)
        ranked.append({**lot, "geo_match": result})
    return sorted(ranked, key=lambda lot: lot["geo_match"]["geo_score"], reverse=True)
