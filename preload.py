"""Production compatibility layer for ObraSignal.

The application owns TED retrieval, normalization, scoring and dashboard
behaviour directly. This module only augments synchronization with validated
national sources; it never replaces TED or changes its semantics.
"""
import app as _app
from national_sources import fetch_national_sources

APP = _app.APP


_original_fetch_base = _app.fetch_base


def fetch_base_with_national_sources():
    """Keep Portugal BASE and add isolated national European connectors."""
    rows = _original_fetch_base()
    rows.extend(fetch_national_sources())
    return rows


# sync_once resolves fetch_base at call time, so replacing the module-level
# function is sufficient without changing the core application implementation.
_app.fetch_base = fetch_base_with_national_sources
