"""Open, future-facing visual tokens and primitives for ObraSignal."""
from __future__ import annotations

from html import escape


TOKENS = {
    "bg": "#F5F8FC",
    "surface": "#FFFFFF",
    "surface_alt": "#EEF4FA",
    "text": "#172033",
    "muted": "#65738B",
    "line": "#D9E3EF",
    "accent": "#2166F3",
    "accent_soft": "#E7F0FF",
    "positive": "#12805C",
    "positive_soft": "#E7F7F1",
    "warning": "#A56B00",
    "warning_soft": "#FFF4DD",
    "negative": "#B42336",
    "negative_soft": "#FDECEF",
}


def visual_css() -> str:
    t = TOKENS
    return f"""
:root {{
  --os-bg: {t['bg']};
  --os-surface: {t['surface']};
  --os-surface-alt: {t['surface_alt']};
  --os-text: {t['text']};
  --os-muted: {t['muted']};
  --os-line: {t['line']};
  --os-accent: {t['accent']};
  --os-accent-soft: {t['accent_soft']};
  --os-positive: {t['positive']};
  --os-positive-soft: {t['positive_soft']};
  --os-warning: {t['warning']};
  --os-warning-soft: {t['warning_soft']};
  --os-negative: {t['negative']};
  --os-negative-soft: {t['negative_soft']};
  --os-radius: 18px;
  --os-shadow: 0 12px 34px rgba(25, 55, 95, .08);
  --os-shadow-soft: 0 4px 16px rgba(25, 55, 95, .06);
}}

* {{ box-sizing: border-box; }}
body {{ margin: 0; background: var(--os-bg); color: var(--os-text); font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
a {{ color: var(--os-accent); text-decoration: none; }}
.os-shell {{ max-width: 1180px; margin: 0 auto; padding: 28px; }}
.os-card {{ background: var(--os-surface); border: 1px solid var(--os-line); border-radius: var(--os-radius); box-shadow: var(--os-shadow-soft); padding: 20px; }}
.os-card--hero {{ box-shadow: var(--os-shadow); }}
.os-kicker {{ color: var(--os-accent); font-size: 12px; font-weight: 800; letter-spacing: .12em; text-transform: uppercase; }}
.os-title {{ margin: 6px 0; font-size: clamp(28px, 4vw, 46px); line-height: 1.05; letter-spacing: -.035em; }}
.os-muted {{ color: var(--os-muted); }}
.os-grid {{ display: grid; gap: 16px; grid-template-columns: repeat(3, minmax(0, 1fr)); }}
.os-pill {{ display: inline-flex; align-items: center; gap: 6px; border-radius: 999px; padding: 7px 11px; font-size: 12px; font-weight: 750; background: var(--os-surface-alt); color: var(--os-text); }}
.os-pill--hot {{ background: var(--os-positive-soft); color: var(--os-positive); }}
.os-pill--review {{ background: var(--os-warning-soft); color: var(--os-warning); }}
.os-pill--reject {{ background: var(--os-negative-soft); color: var(--os-negative); }}
.os-stat {{ font-size: 32px; font-weight: 850; letter-spacing: -.03em; }}
.os-button {{ display: inline-flex; align-items: center; justify-content: center; border: 1px solid var(--os-line); border-radius: 12px; padding: 10px 14px; background: var(--os-surface); color: var(--os-text); font-weight: 750; }}
.os-button--primary {{ border-color: var(--os-accent); background: var(--os-accent); color: white; }}
.os-future {{ background: linear-gradient(135deg, #FFFFFF 0%, #EEF6FF 55%, #F5F8FC 100%); border: 1px solid #CFE0F5; }}
@media (max-width: 860px) {{ .os-grid {{ grid-template-columns: 1fr; }} .os-shell {{ padding: 18px; }} }}
"""


def status_class(status: str | None) -> str:
    value = (status or "").upper()
    if value in {"QUALIFIED", "RELEVANT"}:
        return "os-pill--hot"
    if value == "REVIEW":
        return "os-pill--review"
    if value in {"REJECT", "REJECTED", "LOW_SCORE"}:
        return "os-pill--reject"
    return ""


def render_status_pill(status: str | None) -> str:
    label = escape(str(status or "SEM DECISÃO"))
    return f'<span class="os-pill {status_class(status)}">{label}</span>'
