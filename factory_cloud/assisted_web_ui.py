from __future__ import annotations

import html
import json
from typing import Iterable


_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__</title>
<style>
:root{color-scheme:light dark}body{font-family:system-ui,sans-serif;max-width:860px;margin:2rem auto;padding:0 1rem;line-height:1.45}
form,section{display:grid;gap:.8rem;margin:1.25rem 0;padding:1rem;border:1px solid #8888;border-radius:.65rem}
label{display:grid;gap:.3rem}label.check{display:flex;align-items:flex-start;gap:.6rem}label.check input{margin-top:.25rem}
input,textarea,button{font:inherit;padding:.65rem}button{cursor:pointer;min-height:44px}button[hidden],[hidden]{display:none!important}
pre{white-space:pre-wrap;overflow-wrap:anywhere}.warning{border-left:4px solid currentColor;padding-left:.8rem}
@media (max-width:560px){body{margin:1rem auto}form,section{padding:.8rem}}
</style>
</head>
<body>
<header>
<h1>__TITLE__</h1>
<p><strong>Mode:</strong> assisted, pre-customer certification.</p>
<p>Identity is supplied only by trusted upstream infrastructure. This interface does not allow tenant, actor, role or signature override.</p>
<p class="warning"><strong>Safety:</strong> evidence-backed synthetic/public-shadow inputs only until PILOT_SAFE. A candidate cannot be approved or actioned while entitlement/breach remains unresolved.</p>
</header>
<main>
<form id="analysis-form">
<h2>1. Evidence-backed analysis</h2>
__INPUTS__
<button type="submit">Analyze evidence packet</button>
</form>
<section aria-live="polite" aria-atomic="true">
<h2>Status</h2>
<p id="status">Ready.</p>
<pre id="result"></pre>
</section>
<form id="adjudication-form" hidden>
<h2>2. Human adjudication</h2>
<label class="check"><input name="entitlement_established" type="checkbox"><span>Entitlement established by reviewed evidence</span></label>
__BREACH_CONTROL__
<label>Decision evidence reference<input name="evidence_ref" required></label>
<label>Decision reason<textarea name="reason" required></textarea></label>
<button type="submit">Record adjudication</button>
</form>
<form id="review-form" hidden>
<h2>3. Finding review</h2>
<label>Review reason<textarea name="reason" required></textarea></label>
<button id="approve-button" type="submit" name="approved" value="true">Approve finding</button>
<button type="submit" name="approved" value="false">Reject finding</button>
</form>
<form id="action-form" hidden>
<h2>4. Action</h2>
<button type="submit">Mark adjudicated finding as actioned</button>
</form>
<form id="resolve-form" hidden>
<h2>5. Resolve outcome</h2>
<label>Outcome ID<input name="outcome_id" required></label>
<label>Recovered amount<input name="recovered_amount" inputmode="decimal" required></label>
<label>Currency<input name="currency" value="EUR" maxlength="3" required></label>
<label>Outcome evidence reference<input name="evidence_ref" required></label>
<button type="submit">Record outcome</button>
</form>
</main>
<script>
const fieldSpecs=__FIELDS_JSON__;
const analysisEndpoint=__ENDPOINT_JSON__;
const requiresBreach=__REQUIRES_BREACH__;
let findingId=null;
const statusEl=document.getElementById('status');
const resultEl=document.getElementById('result');
const adjudicationForm=document.getElementById('adjudication-form');
const reviewForm=document.getElementById('review-form');
const approveButton=document.getElementById('approve-button');
const actionForm=document.getElementById('action-form');
const resolveForm=document.getElementById('resolve-form');
function setNested(target,path,value){
  const parts=path.split('.'); let cursor=target;
  for(let i=0;i<parts.length-1;i++){cursor[parts[i]] ??={};cursor=cursor[parts[i]];}
  cursor[parts.at(-1)]=value;
}
async function api(path,options){
  statusEl.textContent='Working…';
  try{
    const response=await fetch(path,options);
    let data={};
    try{data=await response.json();}catch(_jsonError){throw new Error(`Invalid server response (${response.status})`);}
    resultEl.textContent=JSON.stringify(data,null,2);
    if(!response.ok)throw new Error(data.message||`Request failed (${response.status})`);
    statusEl.textContent='Completed.';return data;
  }catch(error){statusEl.textContent=`Error: ${error.message}`;throw error;}
}
document.getElementById('analysis-form').addEventListener('submit',async event=>{
  event.preventDefault(); const form=new FormData(event.currentTarget); const payload={};
  for(const spec of fieldSpecs){setNested(payload,spec.name,spec.type==='checkbox'?form.has(spec.name):form.get(spec.name));}
  try{
    const data=await api(analysisEndpoint,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    findingId=data.finding_id; adjudicationForm.hidden=false; reviewForm.hidden=true; actionForm.hidden=true; resolveForm.hidden=true;
    statusEl.textContent='Candidate created. Human adjudication is required before approval.';
  }catch(_e){}
});
adjudicationForm.addEventListener('submit',async event=>{
  event.preventDefault();if(!findingId)return;const form=new FormData(event.currentTarget);
  const payload={entitlement_established:form.has('entitlement_established'),evidence_ref:form.get('evidence_ref'),reason:form.get('reason')};
  if(requiresBreach)payload.breach_established=form.has('breach_established');
  try{
    const data=await api(`/findings/${encodeURIComponent(findingId)}/adjudicate`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    reviewForm.hidden=false;approveButton.hidden=!data.actionable;
    statusEl.textContent=data.actionable?'Adjudication is actionable. Review may proceed.':'Adjudication is not actionable. Approval remains blocked; rejection is available.';
  }catch(_e){}
});
reviewForm.addEventListener('submit',async event=>{
  event.preventDefault();if(!findingId)return;const submitter=event.submitter;const form=new FormData(event.currentTarget);
  try{const data=await api(`/findings/${encodeURIComponent(findingId)}/review`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({approved:submitter.value==='true',reason:form.get('reason')})});if(data.state==='APPROVED')actionForm.hidden=false;}catch(_e){}
});
actionForm.addEventListener('submit',async event=>{event.preventDefault();if(!findingId)return;try{const data=await api(`/findings/${encodeURIComponent(findingId)}/action`,{method:'POST'});if(data.state==='ACTIONED')resolveForm.hidden=false;}catch(_e){}});
resolveForm.addEventListener('submit',async event=>{event.preventDefault();if(!findingId)return;const form=new FormData(event.currentTarget);const payload={outcome_id:form.get('outcome_id'),recovered_amount:form.get('recovered_amount'),currency:form.get('currency'),evidence_ref:form.get('evidence_ref')};try{await api(`/findings/${encodeURIComponent(findingId)}/resolve`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});}catch(_e){}});
</script>
<footer><small>__VERTICAL__ · evidence-backed assisted workspace · no production authority</small></footer>
</body>
</html>"""


def render_assisted_workspace(
    *,
    title: str,
    vertical: str,
    analysis_fields: Iterable[tuple[str, str, str]],
    analysis_endpoint: str = "/shadow/analyze",
    requires_breach: bool = False,
) -> str:
    """Render a dependency-free evidence-backed assisted workspace."""
    fields = list(analysis_fields)

    def field_html(name: str, label: str, input_type: str) -> str:
        escaped_name = html.escape(name)
        escaped_label = html.escape(label)
        if input_type == "checkbox":
            return (
                f'<label class="check"><input name="{escaped_name}" type="checkbox" required>'
                f'<span>{escaped_label}</span></label>'
            )
        attrs = ""
        if name.endswith("sha256"):
            attrs = ' minlength="64" maxlength="64" pattern="[0-9a-fA-F]{64}" spellcheck="false"'
        return f'<label>{escaped_label}<input name="{escaped_name}" type="{html.escape(input_type)}" required{attrs}></label>'

    inputs = "\n".join(field_html(*field) for field in fields)
    fields_json = json.dumps([{"name": name, "type": input_type} for name, _, input_type in fields])
    breach_control = ""
    if requires_breach:
        breach_control = '<label class="check"><input name="breach_established" type="checkbox"><span>Contractual breach established by reviewed evidence</span></label>'

    return (
        _TEMPLATE
        .replace("__TITLE__", html.escape(title))
        .replace("__VERTICAL__", html.escape(vertical))
        .replace("__INPUTS__", inputs)
        .replace("__BREACH_CONTROL__", breach_control)
        .replace("__FIELDS_JSON__", fields_json)
        .replace("__ENDPOINT_JSON__", json.dumps(analysis_endpoint))
        .replace("__REQUIRES_BREACH__", "true" if requires_breach else "false")
    )
