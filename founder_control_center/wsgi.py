"""Production WSGI entrypoint for the Founder Control Center."""

from .app import APP as app
from .retention import install_snapshot_retention

SNAPSHOT_RETENTION = install_snapshot_retention()
