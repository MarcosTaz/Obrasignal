#!/usr/bin/env python3
"""Stable customer-facing search metadata for the published ObraSignal landing.

The build SHA remains in the private release marker and `release-source.txt`,
never in the public <title>. This module has no networking or deployments.
"""
from __future__ import annotations

from html import escape
from pathlib import Path
from urllib.parse import urlparse
import re

CANONICAL_URL = "https://obrasignal.com/"
PUBLIC_TITLE = "ObraSignal | Inteligência em Contratação Pública"
PUBLIC_DESCRIPTION = (
    "A ObraSignal identifica e prioriza oportunidades de contratação pública "
    "alinhadas com a sua empresa, explica a relevância e apoia decisões comerciais."
)
_META_KEYS = frozenset({
    "description", "og:title", "og:description", "og:type", "og:url",
    "og:site_name", "twitter:card", "twitter:title", "twitter:description",
})


def _attribute(tag: str, name: str) -> str | None:
    match = re.search(r"\b" + re.escape(name) + r"\s*=\s*([\"'])(.*?)\1", tag, re.I | re.S)
    return match.group(2) if match else None


def stamp_public_seo(html: str) -> str:
    """Add crawlable SEO tags to Expo's initial HTML, even without JavaScript."""
    if not re.search(r"</head\s*>", html, re.I):
        raise ValueError("Public SEO metadata requires a complete HTML head")
    # A public production page must not accidentally override a deliberate noindex.
    for match in re.finditer(r"<meta\b[^>]*>", html, re.I):
        tag = match.group()
        if (_attribute(tag, "name") or "").lower() in ("robots", "googlebot"):
            if "noindex" in (_attribute(tag, "content") or "").lower():
                raise ValueError("Refusing to publish indexable canonical on a noindex page")
    if "<!-- Stable official public identity; commit SHA only in release metadata. -->" in html:
        return html  # Idempotent when stamping an existing verified build.
    html = re.sub(r"<title\b[^>]*>.*?</title\s*>", "", html, flags=re.I | re.S)

    def remove_prior_meta(match):
        tag = match.group()
        key = (_attribute(tag, "name") or _attribute(tag, "property") or "").lower()
        return "" if key in _META_KEYS else tag

    html = re.sub(r"<meta\b[^>]*>", remove_prior_meta, html, flags=re.I)

    def remove_prior_canonical(match):
        tag = match.group()
        rel = (_attribute(tag, "rel") or "").lower().split()
        return "" if "canonical" in rel else tag

    html = re.sub(r"<link\b[^>]*>", remove_prior_canonical, html, flags=re.I)
    meta = (
        "\n  <!-- Stable official public identity; commit SHA only in release metadata. -->"
        f"\n  <title>{escape(PUBLIC_TITLE)}</title>"
        f"\n  <meta name=\"description\" content=\"{escape(PUBLIC_DESCRIPTION, quote=True)}\">"
        f"\n  <link rel=\"canonical\" href=\"{CANONICAL_URL}\">"
        f"\n  <meta property=\"og:title\" content=\"{escape(PUBLIC_TITLE, quote=True)}\">"
        f"\n  <meta property=\"og:description\" content=\"{escape(PUBLIC_DESCRIPTION, quote=True)}\">"
        f"\n  <meta property=\"og:url\" content=\"{CANONICAL_URL}\">"
        "\n  <meta property=\"og:type\" content=\"website\">"
        "\n  <meta property=\"og:site_name\" content=\"ObraSignal\">"
        "\n  <meta name=\"twitter:card\" content=\"summary\">"
        f"\n  <meta name=\"twitter:title\" content=\"{escape(PUBLIC_TITLE, quote=True)}\">"
        f"\n  <meta name=\"twitter:description\" content=\"{escape(PUBLIC_DESCRIPTION, quote=True)}\">"
        "\n"
    )
    return re.sub(r"</head\s*>", lambda _: meta + "</head>", html, count=1, flags=re.I)


def write_public_discovery_files(export_dir: Path) -> None:
    """Publish only the one known public landing URL; never disclose private routes."""
    export_dir = Path(export_dir)
    if not (export_dir / "index.html").is_file():
        raise ValueError("Missing exported index.html; refusing search assets")
    url = urlparse(CANONICAL_URL)
    if url.scheme != "https" or not url.hostname:
        raise ValueError("Invalid canonical URL")
    (export_dir / "robots.txt").write_text(
        "User-agent: *\nAllow: /\nSitemap: " + CANONICAL_URL + "sitemap.xml\n",
        encoding="utf-8",
    )
    (export_dir / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        '<url><loc>' + CANONICAL_URL + '</loc></url></urlset>\n',
        encoding="utf-8",
    )


def validate_public_seo(export_dir: Path) -> None:
    """Build-time guard; the URL and full human title must be exactly stable."""
    export_dir = Path(export_dir)
    html = (export_dir / "index.html").read_text(encoding="utf-8")
    if len(re.findall(r"<title\b", html, flags=re.I)) != 1:
        raise ValueError("Public page must have exactly one title")
    if f"<title>{PUBLIC_TITLE}</title>" not in html:
        raise ValueError("Public page title must never contain a commit SHA")
    for required in (
        f'<link rel="canonical" href="{CANONICAL_URL}">',
        '<meta name="description"',
        '<meta property="og:title"',
        '<meta property="og:url"',
        '<meta name="twitter:card"',
    ):
        if required not in html:
            raise ValueError("Missing public SEO field: " + required)
    if not (export_dir / "robots.txt").is_file() or not (export_dir / "sitemap.xml").is_file():
        raise ValueError("Missing public search discovery files")
    if CANONICAL_URL not in (export_dir / "sitemap.xml").read_text(encoding="utf-8"):
        raise ValueError("Sitemap does not refer to official domain")


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        raise SystemExit("Usage: public_web_seo.py <web-export-dir>")
    validate_public_seo(Path(sys.argv[1]))
    print("PASS: ObraSignal stable public title, canonical, metadata and discovery files")
