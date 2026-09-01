"""Runnable WSGI entrypoint for the EU Cloud Switching pilot lane.

This intentionally does not replace the canonical ObraSignal production WSGI
entrypoint. It allows the Factory branch to run and validate the pilot safely
while canonical integration remains a separate reviewed change.
"""
from __future__ import annotations

import os
from pathlib import Path

from cloud_switching.standalone import create_app

DATABASE_PATH = os.getenv(
    "CLOUD_SWITCHING_DB",
    os.getenv("OBRASIGNAL_DB", str(Path(__file__).with_name("cloud_switching.db"))),
)

APP = create_app(database_path=DATABASE_PATH)
