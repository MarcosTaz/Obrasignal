"""Explainable matching of procurement lots against a company profile."""

from commercial_score_v2 import score_v2
from geo_profile import geographic_fit


def _location_result(location, profile):
    item = {
        "country_code": location.get("country") or location.get("country_code"),
        "nuts_codes": ([location.get("nuts3")] if location.get("nuts3") else location.get("nuts_codes") or []),
        "city": location.get("city"),
        "postal_code": location.get("postcode") or location.get("postal_code"),
        "regions": location.get("regions") or location.get("region_codes") or [],
        "region": location.get("region") or location.get("subdivision") or location.get("nuts_region"),
        "latitude": location.get("latitude", location.get("lat")),
        "longitude": location.get("longitude", location.get("lon", location.get("lng"))),
    }
    result = geographic_fit(item, profile)
    if location.get("broad") and result["reason"] == "localização insuficiente":
        return {"score": 2, "confidence": 50, "reason": "área geográfica ampla"}
    return result


def match_lot(lot, profile):
    """Score one lot without discarding incomplete information."""
    item = dict(lot or {})
    commercial = score_v2(item)
    locations = item.get("locations") or []
    geo_matches = [_location_result(location, profile) for location in locations]
    if geo_matches:
        geo = max(geo_matches, key=lambda x: (x["score"], x.get("confidence", 0)))
    else:
        geo = {"score": 2, "confidence": 20, "reason": "localização insuficiente"}
    score = max(0, min(100, commercial["score"] - 5 + geo["score"]))
    if score >= 80:
        match = "EXCELLENT_MATCH"
    elif score >= 65:
        match = "GOOD_MATCH"
    elif score >= 50:
        match = "POSSIBLE_MATCH"
    else:
        match = "POOR_MATCH"
    return {
        "lot_id": item.get("lot_id") or item.get("technical_lot_id"),
        "score": score,
        "match": match,
        "commercial": commercial,
        "geography": geo,
        "all_geography_matches": geo_matches,
    }


def match_notice_lots(lots, profile):
    """Return all lot evaluations, best lot, and runner-up in deterministic order."""
    results = [match_lot(lot, profile) for lot in (lots or [])]
    results.sort(key=lambda r: (-r["score"], str(r.get("lot_id") or "")))
    return {
        "lots": results,
        "best_lot": results[0] if results else None,
        "second_best_lot": results[1] if len(results) > 1 else None,
    }
