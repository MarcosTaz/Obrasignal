"""Production WSGI entrypoint with a global CORS safety net.

The API blueprint already handles CORS, but browser preflight must be answered
before authentication and before any blueprint-specific hook can interfere.
This wrapper makes that guarantee at the application boundary.
"""
import os
from urllib.parse import urlsplit, urlunsplit

from flask import request

from api import APP


def _origin():
    value = (os.getenv("OBRASIGNAL_CORS_ORIGIN") or "https://marcostaz.github.io").strip()
    if value == "*":
        return value
    parsed = urlsplit(value)
    if not parsed.scheme or not parsed.netloc:
        return None
    return urlunsplit((parsed.scheme, parsed.netloc, "", "", ""))


def _cors(response):
    origin = _origin()
    if origin:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Vary"] = "Origin"
    response.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type, X-ObraSignal-Version"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Max-Age"] = "600"
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-ObraSignal-API"] = "v1"
    return response


@APP.before_request
def _global_api_preflight():
    if request.path.startswith("/api/v1/") and request.method == "OPTIONS":
        response = APP.response_class("", status=204, mimetype="text/plain")
        return _cors(response)
    return None


@APP.after_request
def _global_api_cors(response):
    if request.path.startswith("/api/v1/"):
        return _cors(response)
    return response
