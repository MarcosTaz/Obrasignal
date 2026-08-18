"""Profile-aware geographic fit for procurement opportunities."""

from math import asin, cos, radians, sin, sqrt

DEFAULT_PROFILE = {
    "countries": {"PRT"},
    "nuts": set(),
    "cities": set(),
    "postal_prefixes": set(),
    "regions": set(),
    "geographic_radius_km": None,
}


def _norm(value):
    return str(value or "").strip().upper()


def _norm_set(values):
    return {_norm(value) for value in (values or set()) if _norm(value)}


def _haversine_km(lat1, lon1, lat2, lon2):
    """Return great-circle distance in km for valid coordinate pairs."""
    try:
        lat1, lon1, lat2, lon2 = map(float, (lat1, lon1, lat2, lon2))
    except (TypeError, ValueError):
        return None
    if not (-90 <= lat1 <= 90 and -90 <= lat2 <= 90 and -180 <= lon1 <= 180 and -180 <= lon2 <= 180):
        return None
    rlat1, rlon1, rlat2, rlon2 = map(radians, (lat1, lon1, lat2, lon2))
    dlat = rlat2 - rlat1
    dlon = rlon2 - rlon1
    a = sin(dlat / 2) ** 2 + cos(rlat1) * cos(rlat2) * sin(dlon / 2) ** 2
    return 6371.0088 * 2 * asin(sqrt(a))


def _reference_points(profile):
    points = []
    for point in profile.get("profile_coordinates", []) or []:
        if not isinstance(point, dict):
            continue
        lat = point.get("latitude", point.get("lat"))
        lon = point.get("longitude", point.get("lon", point.get("lng")))
        if lat is not None and lon is not None:
            points.append((lat, lon))
    return points


def geographic_fit(item, profile=None):
    profile = {**DEFAULT_PROFILE, **(profile or {})}
    countries = _norm_set(profile.get("countries"))
    nuts = _norm_set(profile.get("nuts"))
    cities = _norm_set(profile.get("cities"))
    prefixes = _norm_set(profile.get("postal_prefixes"))
    regions = _norm_set(profile.get("regions"))

    item_country = _norm(item.get("country_code") or item.get("place_country"))
    item_nuts = {_norm(x) for x in (item.get("nuts_codes") or [])}
    item_city = _norm(item.get("city") or item.get("place_city"))
    postcode = _norm(item.get("postal_code") or item.get("place_postal_code"))
    item_regions = {_norm(x) for x in (item.get("regions") or item.get("place_regions") or [])}
    direct_region = _norm(item.get("region") or item.get("place_region"))

    if countries and item_country in countries:
        if nuts and item_nuts & nuts:
            return {"score": 5, "confidence": 100, "reason": "NUTS prioritário"}
        if cities and item_city in cities:
            return {"score": 5, "confidence": 100, "reason": "cidade prioritária"}
        if prefixes and any(postcode.startswith(p) for p in prefixes):
            return {"score": 5, "confidence": 100, "reason": "código postal prioritário"}
        if regions and ((direct_region and direct_region in regions) or item_regions & regions):
            return {"score": 5, "confidence": 100, "reason": "região prioritária"}

        radius = profile.get("geographic_radius_km")
        if radius is not None:
            item_lat = item.get("latitude", item.get("lat"))
            item_lon = item.get("longitude", item.get("lon", item.get("lng")))
            distances = [_haversine_km(item_lat, item_lon, lat, lon) for lat, lon in _reference_points(profile)]
            distances = [value for value in distances if value is not None]
            if distances:
                distance = min(distances)
                if distance <= float(radius):
                    return {
                        "score": 5,
                        "confidence": 100,
                        "reason": f"dentro do raio geográfico ({distance:.1f} km)",
                        "distance_km": round(distance, 1),
                    }
                return {
                    "score": 1,
                    "confidence": 100,
                    "reason": f"fora do raio geográfico ({distance:.1f} km)",
                    "distance_km": round(distance, 1),
                }

        return {"score": 3, "confidence": 80, "reason": "país compatível"}

    if item_country and countries:
        return {"score": 0, "confidence": 100, "reason": "país fora do perfil"}

    return {"score": 2, "confidence": 20, "reason": "localização insuficiente"}
