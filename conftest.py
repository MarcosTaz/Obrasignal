"""Pytest-wide isolation for background worker side effects."""
from __future__ import annotations

import os

# Development identity is a deliberate test contract, never an absent-config
# fallback. Individual auth tests may delete/override this variable explicitly.
os.environ.setdefault("OBRASIGNAL_AUTH_MODE", "development")

import app

# Production WSGI startup explicitly calls ``start_background_worker``. Tests
# import application modules for request-level assertions and must never spawn a
# daemon that performs live network ingestion or holds SQLite locks.
app._worker_started = True
