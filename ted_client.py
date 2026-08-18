"""Resilient transport for the public TED Search API.

The Search API is public and rate-limited. Keep retry policy here so ingestion
code stays focused on query construction and normalization.
"""
import time
import requests

RETRYABLE_STATUS = {429, 500, 502, 503, 504}


def post_json(url, *, json, timeout=45, session=None, retries=3, backoff=1.0):
    """POST JSON with bounded retries for transient transport/API failures."""
    session = session or requests
    last = None
    for attempt in range(retries + 1):
        try:
            response = session.post(url, json=json, timeout=timeout)
            if response.status_code not in RETRYABLE_STATUS:
                response.raise_for_status()
                return response.json()
            last = response
        except (requests.Timeout, requests.ConnectionError) as exc:
            last = exc
        if attempt >= retries:
            if isinstance(last, Exception):
                raise last
            last.raise_for_status()
        time.sleep(backoff * (2 ** attempt))
    raise RuntimeError("TED request failed without a response")
