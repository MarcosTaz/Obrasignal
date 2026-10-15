#!/usr/bin/env python3
"""Fail deployment when canonical Pages HTML references missing or repository-prefixed assets."""
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse, unquote

class Assets(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = []
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "script" and a.get("src"):
            self.urls.append(a["src"])
        if tag == "link" and a.get("rel") in ("stylesheet", "modulepreload") and a.get("href"):
            self.urls.append(a["href"])

def verify(folder):
    root = Path(folder).resolve()
    html = root / "index.html"
    if not html.is_file():
        raise ValueError("Missing index.html")
    parser = Assets()
    parser.feed(html.read_text(encoding="utf-8"))
    if not parser.urls:
        raise ValueError("No script or stylesheet assets found")
    issues = []
    for url in parser.urls:
        parsed = urlparse(url)
        if parsed.scheme or parsed.netloc:
            continue
        path = unquote(parsed.path)
        if path.startswith("/Obrasignal/"):
            issues.append(f"legacy subpath in canonical build: {url}")
            continue
        candidate = (root / path.lstrip("/")).resolve()
        if not candidate.is_relative_to(root) or not candidate.is_file():
            issues.append(f"missing published asset: {url}")
    if issues:
        raise ValueError("; ".join(issues))
    print(f"PASS: {len(parser.urls)} canonical HTML assets checked against {root}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: verify_pages_bundle_paths.py <export-dir>")
    try:
        verify(sys.argv[1])
    except ValueError as error:
        print(f"FAIL: {error}", file=sys.stderr)
        raise SystemExit(1)
