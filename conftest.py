"""Pytest-wide isolation for process-level background ingestion.

The production WSGI entrypoint starts the ingestion worker on import. Some tests
import that entrypoint during collection; without this guard a daemon sync can
race later transport tests and consume their monkeypatched HTTP calls.

Mark the worker as already started before test modules are collected. Production
code is unchanged; this file is loaded by pytest only.
"""
import app


app._worker_started = True
