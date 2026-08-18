"""Production compatibility layer for ObraSignal.

The application now owns TED retrieval, normalization, scoring and dashboard
behaviour directly. This module intentionally does not override those functions
so production uses the same European TED logic as development/CI.
"""
import app as _app

APP = _app.APP
