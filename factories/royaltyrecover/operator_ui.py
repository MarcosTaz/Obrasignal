from __future__ import annotations

from html import escape

from flask import Blueprint, Response, request

from finding_store import FindingStore
from outcome_store import OutcomeStore
from repository import RoyaltyRepository


def _money(amount, currency):
    if amount is None:
        return "—"
    return f"{escape(str(currency or ''))} {escape(str(amount))}".strip()


def _page(org_id: str, summary: dict, recovery_summary: dict, items: list[dict]) -> str:
    rows = []
    for item in items:
        rows.append(
            "<tr>"
            f"<td>{escape(item['licensee_name'])}</td>"
            f"<td>{escape(item['agreement_title'])}</td>"
            f"<td><span class='pill'>{escape(item['state'])}</span></td>"
            f"<td>{escape(item['review_status'])}</td>"
            f"<td class='money'>{_money(item['amount_decimal'], item['currency'])}</td>"
            f"<td>{'No' if not item['claim_ready'] else 'Yes'}</td>"
            "</tr>"
        )
    body_rows = "".join(rows) or "<tr><td colspan='6' class='empty'>No persisted findings yet.</td></tr>"
    candidate_total = _money(summary.get("analytical_candidate_total"), summary.get("analytical_candidate_currency"))
    if summary.get("mixed_currency_total_suppressed"):
        candidate_total = "Suppressed — mixed currencies"
    verified_total = _money(recovery_summary.get("verified_recovery_total"), recovery_summary.get("currency"))
    if recovery_summary.get("mixed_currency_total_suppressed"):
        verified_total = "Suppressed — mixed currencies"
    return f"""<!doctype html>
<html lang='en'>
<head>
<meta charset='utf-8'>
<meta name='viewport' content='width=device-width,initial-scale=1'>
<title>RoyaltyRecover — Recoverability Register</title>
<style>
:root{{--bg:#f5f6f8;--panel:#fff;--text:#17202a;--muted:#667085;--line:#e4e7ec;--warn:#8a4b08;--ok:#186a3b}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--text);font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}}
main{{max-width:1180px;margin:0 auto;padding:32px 20px 56px}} header{{display:flex;justify-content:space-between;align-items:flex-start;gap:24px;margin-bottom:28px}}
h1{{font-size:28px;margin:0 0 8px}} h2{{margin-top:28px}} p{{margin:0;color:var(--muted);line-height:1.5}} .org{{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12px;color:var(--muted)}}
.grid{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px;margin:22px 0}} .card{{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:18px}}
.metric{{font-size:25px;font-weight:700;margin-top:8px}} .label{{font-size:13px;color:var(--muted)}} .verified .metric{{color:var(--ok)}} .notice{{border-left:4px solid var(--warn);padding:13px 16px;background:#fff8ef;border-radius:8px;margin:18px 0 24px;color:#5f3a11}}
.table-wrap{{overflow:auto;background:var(--panel);border:1px solid var(--line);border-radius:14px}} table{{width:100%;border-collapse:collapse;min-width:860px}} th,td{{padding:13px 14px;text-align:left;border-bottom:1px solid var(--line);font-size:13px}} th{{color:var(--muted);font-weight:600;background:#fafafa}} tr:last-child td{{border-bottom:0}} .pill{{display:inline-block;border:1px solid var(--line);border-radius:999px;padding:4px 8px;font-size:11px;font-weight:600}} .money{{font-variant-numeric:tabular-nums}} .empty{{text-align:center;color:var(--muted);padding:32px}}
footer{{margin-top:20px;font-size:12px;color:var(--muted)}} @media(max-width:900px){{.grid{{grid-template-columns:repeat(2,1fr)}}}} @media(max-width:560px){{.grid{{grid-template-columns:1fr}} header{{display:block}}}}
</style>
</head>
<body><main>
<header><div><h1>RoyaltyRecover</h1><p>Evidence-first recoverability register</p></div><div class='org'>Organization: {escape(org_id)}</div></header>
<section class='grid' aria-label='Portfolio summary'>
<div class='card'><div class='label'>Persisted findings</div><div class='metric'>{summary['finding_count']}</div></div>
<div class='card'><div class='label'>Analytical candidate total</div><div class='metric'>{candidate_total}</div></div>
<div class='card verified'><div class='label'>Verified paid recovery</div><div class='metric'>{verified_total}</div><div class='label'>{recovery_summary['verified_recovery_count']} verified record(s)</div></div>
<div class='card'><div class='label'>Claim-ready</div><div class='metric'>0</div></div>
</section>
<div class='notice'><strong>Analytical triage is not recovery.</strong> Candidate amounts remain separate from verified paid recovery. A positive variance is not a legal claim, formal audit conclusion, auditor acceptance, or recovered cash.</div>
<section><h2>Recoverability register</h2><div class='table-wrap'><table>
<thead><tr><th>Licensee</th><th>Agreement</th><th>State</th><th>Review</th><th>Analytical amount</th><th>Claim-ready</th></tr></thead>
<tbody>{body_rows}</tbody></table></div></section>
<footer>Raw agreement and evidence contents are not rendered on this screen. Analytical amounts come only from deterministic persisted scans; verified recovery requires separate external outcome and payment evidence.</footer>
</main></body></html>"""


def create_operator_blueprint(repository: RoyaltyRepository) -> Blueprint:
    bp = Blueprint("royaltyrecover_operator", __name__)
    findings = FindingStore(repository)
    outcomes = OutcomeStore(repository)

    @bp.get("/app")
    def operator_dashboard():
        org_id = request.royaltyrecover_org_id
        summary = findings.register_summary(org_id)
        recovery_summary = outcomes.verified_summary(org_id)
        items = findings.recoverability_register(org_id)
        return Response(_page(org_id, summary, recovery_summary, items), mimetype="text/html")

    return bp
