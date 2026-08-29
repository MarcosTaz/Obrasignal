from __future__ import annotations

import html
import json
from typing import Iterable


def render_assisted_workspace(*, title: str, vertical: str, analysis_fields: Iterable[tuple[str, str, str]]) -> str:
    """Render a dependency-free assisted workspace over the existing JSON API.

    Tenant/actor identity is intentionally absent from the page: trusted upstream
    infrastructure remains the only identity authority. The page never grants
    production or customer-data authority and is suitable for synthetic/shadow use.
    """
    fields = list(analysis_fields)
    inputs = "\n".join(
        f'<label>{html.escape(label)}<input name="{html.escape(name)}" type="{html.escape(input_type)}" required></label>'
        for name, label, input_type in fields
    )
    names_json = json.dumps([name for name, _, _ in fields])
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title>
<style>
body{{font-family:system-ui,sans-serif;max-width:760px;margin:2rem auto;padding:0 1rem;line-height:1.45}}
form,section{{display:grid;gap:.75rem;margin:1.25rem 0;padding:1rem;border:1px solid #bbb;border-radius:.5rem}}
label{{display:grid;gap:.25rem}}input,textarea,button{{font:inherit;padding:.6rem}}button{{cursor:pointer}}
[hidden]{{display:none}} pre{{white-space:pre-wrap;overflow-wrap:anywhere}}
</style>
</head>
<body>
<header>
<h1>{html.escape(title)}</h1>
<p><strong>Mode:</strong> assisted, pre-customer certification.</p>
<p>Identity is supplied only by trusted upstream infrastructure. This interface does not allow tenant or actor override.</p>
<p><strong>Safety:</strong> synthetic/shadow evidence only until PILOT_SAFE.</p>
</header>
<main>
<form id="analysis-form">
<h2>Analyze</h2>
{inputs}
<button type="submit">Analyze evidence</button>
</form>
<section aria-live="polite" aria-atomic="true">
<h2>Status</h2>
<p id="status">Ready.</p>
<pre id="result"></pre>
</section>
<form id="review-form" hidden>
<h2>Human review</h2>
<label>Reason<textarea name="reason" required></textarea></label>
<button type="submit" name="approved" value="true">Approve finding</button>
<button type="submit" name="approved" value="false">Reject finding</button>
</form>
<form id="action-form" hidden>
<h2>Action</h2>
<button type="submit">Mark approved finding as actioned</button>
</form>
<form id="resolve-form" hidden>
<h2>Resolve outcome</h2>
<label>Outcome ID<input name="outcome_id" required></label>
<label>Recovered amount<input name="recovered_amount" inputmode="decimal" required></label>
<label>Currency<input name="currency" value="EUR" maxlength="3" required></label>
<label>Evidence reference<input name="evidence_ref" required></label>
<button type="submit">Record outcome</button>
</form>
</main>
<script>
const fieldNames={names_json};
let findingId=null;
const statusEl=document.getElementById('status');
const resultEl=document.getElementById('result');
const reviewForm=document.getElementById('review-form');
const actionForm=document.getElementById('action-form');
const resolveForm=document.getElementById('resolve-form');
async function api(path, options){{
  statusEl.textContent='Working…';
  try{{
    const response=await fetch(path, options);
    const data=await response.json();
    resultEl.textContent=JSON.stringify(data,null,2);
    if(!response.ok) throw new Error(data.message || `Request failed (${{response.status}})`);
    statusEl.textContent='Completed.';
    return data;
  }}catch(error){{
    statusEl.textContent=`Error: ${{error.message}}`;
    throw error;
  }}
}}
document.getElementById('analysis-form').addEventListener('submit',async event=>{{
  event.preventDefault();
  const form=new FormData(event.currentTarget); const payload={{}};
  for(const name of fieldNames) payload[name]=form.get(name);
  try{{const data=await api('/analyze',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(payload)}});findingId=data.finding_id;reviewForm.hidden=false;}}catch(_e){{}}
}});
reviewForm.addEventListener('submit',async event=>{{
  event.preventDefault(); if(!findingId)return;
  const submitter=event.submitter; const form=new FormData(event.currentTarget);
  try{{const data=await api(`/findings/${{encodeURIComponent(findingId)}}/review`,{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{approved:submitter.value==='true',reason:form.get('reason')}})}});if(data.state==='APPROVED')actionForm.hidden=false;}}catch(_e){{}}
}});
actionForm.addEventListener('submit',async event=>{{event.preventDefault();if(!findingId)return;try{{const data=await api(`/findings/${{encodeURIComponent(findingId)}}/action`,{{method:'POST'}});if(data.state==='ACTIONED')resolveForm.hidden=false;}}catch(_e){{}}}});
resolveForm.addEventListener('submit',async event=>{{event.preventDefault();if(!findingId)return;const form=new FormData(event.currentTarget);const payload={{outcome_id:form.get('outcome_id'),recovered_amount:form.get('recovered_amount'),currency:form.get('currency'),evidence_ref:form.get('evidence_ref')}};try{{await api(`/findings/${{encodeURIComponent(findingId)}}/resolve`,{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(payload)}});}}catch(_e){{}}}});
</script>
<footer><small>{html.escape(vertical)} · assisted workspace · no production authority</small></footer>
</body>
</html>"""
