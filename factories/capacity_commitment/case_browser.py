from __future__ import annotations

from html import escape
from urllib.parse import quote


def render_case_browser(case_ids: list[str]) -> str:
    """Render a minimal authenticated case index from tenant-scoped IDs only."""

    rows = []
    for case_id in case_ids:
        label = escape(case_id, quote=True)
        encoded = quote(case_id, safe="")
        rows.append(
            "<li><code>"
            + label
            + "</code> "
            + f'<a href="/api/capacity/cases/{encoded}">JSON</a> · '
            + f'<a href="/api/capacity/cases/{encoded}/report" target="_blank" rel="noopener">buyer-ready report</a>'
            + "</li>"
        )

    content = "\n".join(rows) if rows else "<li>No cases recorded for this tenant.</li>"
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Capacity Commitment — Existing cases</title>
  <style>
    :root{{color-scheme:dark;--bg:#0b1020;--panel:#121a2d;--line:#263451;--text:#eef3ff;--muted:#9dadca;--accent:#8ee8c8}}
    body{{margin:0;background:var(--bg);color:var(--text);font:14px/1.5 system-ui,-apple-system,sans-serif}}
    main{{max-width:920px;margin:auto;padding:32px 20px}}a{{color:var(--accent)}}
    .panel{{border:1px solid var(--line);background:var(--panel);padding:18px;border-radius:14px}}
    .muted{{color:var(--muted)}}li{{margin:10px 0}}code{{word-break:break-all}}
  </style>
</head>
<body><main>
  <p><a href="/">← New assessment</a></p>
  <h1>Existing Capacity Commitment cases</h1>
  <p class="muted">Only case IDs available to the authenticated tenant are listed. Opening a case recomputes the result from persisted source state under the current matching engine version; it does not prove recovery or payment.</p>
  <section class="panel"><ul>{content}</ul></section>
</main></body></html>"""
