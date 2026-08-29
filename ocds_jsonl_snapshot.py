"""Reusable transport for OCDS compiled-release JSONL gzip snapshots.

Some official publishers expose complete or periodic OCDS snapshots rather than
an append-only API. This transport deliberately re-reads the selected snapshot
on each run: publishers can update an older contracting process as it moves
through its lifecycle, so treating the file as immutable would lose changes.
Stable OCDS OCIDs plus ObraSignal persistence provide idempotency downstream.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
import gzip
import io
import json

import requests


@dataclass(frozen=True)
class OCDSJSONLGzipConfig:
    source: str
    country: str
    url_template: str
    market: str = "GLOBAL"
    timeout: int = 60
    max_compressed_bytes: int = 64 * 1024 * 1024
    max_uncompressed_bytes: int = 256 * 1024 * 1024
    max_records: int = 250_000


class OCDSJSONLGzipSnapshotConnector:
    """Fetch and normalize one bounded year snapshot of compiled OCDS releases."""

    def __init__(self, config, *, session=None):
        self.config = config
        self.session = session or requests.Session()
        self.session.headers.setdefault("User-Agent", "ObraSignal/1.0")

    @staticmethod
    def _year(value):
        if value is None:
            value = datetime.now(timezone.utc)
        if isinstance(value, datetime):
            return value.year
        try:
            year = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("snapshot year must be an integer") from exc
        if year < 2000 or year > 2200:
            raise ValueError("snapshot year is outside the supported range")
        return year

    def _download(self, url):
        response = self.session.get(url, timeout=self.config.timeout, stream=True)
        response.raise_for_status()
        declared = response.headers.get("Content-Length")
        if declared:
            try:
                if int(declared) > self.config.max_compressed_bytes:
                    raise RuntimeError("OCDS snapshot exceeds compressed size limit")
            except ValueError:
                pass

        body = bytearray()
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            if not chunk:
                continue
            body.extend(chunk)
            if len(body) > self.config.max_compressed_bytes:
                raise RuntimeError("OCDS snapshot exceeds compressed size limit")
        if not body:
            raise RuntimeError("OCDS snapshot returned an empty body")
        return bytes(body)

    def fetch_snapshot(self, normalizer, *, year=None, now=None):
        snapshot_year = self._year(year if year is not None else now)
        url = self.config.url_template.format(year=snapshot_year)
        compressed = self._download(url)

        rows = []
        parsed_records = 0
        uncompressed_bytes = 0
        try:
            stream = gzip.GzipFile(fileobj=io.BytesIO(compressed), mode="rb")
            text_stream = io.TextIOWrapper(stream, encoding="utf-8")
            for line_number, line in enumerate(text_stream, start=1):
                uncompressed_bytes += len(line.encode("utf-8"))
                if uncompressed_bytes > self.config.max_uncompressed_bytes:
                    raise RuntimeError("OCDS snapshot exceeds uncompressed size limit")
                text = line.strip()
                if not text:
                    continue
                parsed_records += 1
                if parsed_records > self.config.max_records:
                    raise RuntimeError("OCDS snapshot exceeds record limit")
                try:
                    payload = json.loads(text)
                except json.JSONDecodeError as exc:
                    raise RuntimeError(f"invalid OCDS JSONL at line {line_number}") from exc
                if not isinstance(payload, dict):
                    raise RuntimeError(f"OCDS JSONL line {line_number} is not an object")

                # OCP Data Registry JSONL exports represent each contracting
                # process as a compiled release. Accept an already-wrapped OCDS
                # record too, which keeps this transport reusable for publishers
                # that export the record shape directly.
                if isinstance(payload.get("compiledRelease"), dict):
                    record = payload
                else:
                    record = {
                        "ocid": payload.get("ocid"),
                        "compiledRelease": payload,
                        "_package_uri": url,
                    }
                item = normalizer(record)
                if item is not None:
                    rows.append(item)
        except (OSError, EOFError) as exc:
            raise RuntimeError("OCDS snapshot is not valid gzip data") from exc

        if parsed_records == 0:
            raise RuntimeError("OCDS snapshot contained no JSON records")

        cursor = json.dumps(
            {"snapshot_year": snapshot_year},
            separators=(",", ":"),
            sort_keys=True,
        )
        return rows, cursor
