OPERATOR_HTML = r'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Capacity Commitment — Assisted Recoverability</title>
  <style>
    :root{color-scheme:dark;--bg:#0b1020;--panel:#121a2d;--line:#263451;--text:#eef3ff;--muted:#9dadca;--accent:#8ee8c8;--warn:#ffd37c}
    *{box-sizing:border-box} body{margin:0;background:var(--bg);color:var(--text);font:14px/1.45 system-ui,-apple-system,sans-serif}
    main{max-width:1180px;margin:auto;padding:32px 20px 64px} h1{margin:0 0 6px;font-size:28px} h2{font-size:17px;margin:0 0 14px}
    .sub{color:var(--muted);max-width:820px;margin-bottom:22px}.notice{border:1px solid var(--line);background:#0e1728;padding:12px 14px;border-radius:10px;margin:0 0 22px;color:var(--warn)}
    form{display:grid;gap:16px}.panel{border:1px solid var(--line);background:var(--panel);padding:18px;border-radius:14px}.grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}
    label{display:grid;gap:6px;color:var(--muted);font-size:12px}input,select,textarea{width:100%;border:1px solid var(--line);border-radius:8px;background:#0a1222;color:var(--text);padding:10px;font:inherit}
    textarea{min-height:80px;resize:vertical}.wide{grid-column:span 2}.full{grid-column:1/-1}button{border:0;border-radius:9px;background:var(--accent);color:#07120f;font-weight:750;padding:12px 18px;cursor:pointer;width:max-content}
    button:disabled{opacity:.55;cursor:wait}.result{margin-top:20px;display:none}.metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}.metric{padding:14px;background:#0b1425;border:1px solid var(--line);border-radius:10px}.metric b{display:block;font-size:19px;margin-top:4px}.state{font-weight:800}.small{font-size:12px;color:var(--muted)}pre{white-space:pre-wrap;word-break:break-word;background:#08101d;border:1px solid var(--line);padding:12px;border-radius:9px;max-height:360px;overflow:auto}
    @media(max-width:850px){.grid,.metrics{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:520px){.grid,.metrics{grid-template-columns:1fr}.wide{grid-column:auto}}
  </style>
</head>
<body>
<main>
  <h1>Capacity Commitment</h1>
  <div class="sub">Assisted volume-shortfall & dedicated-investment recoverability assessment. Economic exposure is kept separate from contractual support, claimability, settlement and payment.</div>
  <div class="notice">Unknown stays unknown. No result on this screen is a verified recovery or payment. Positive recoverability still requires authorized human review before external submission.</div>
  <form id="case-form">
    <section class="panel"><h2>1 — Company / program / contract anchor</h2><div class="grid">
      <label>Company ID<input name="company_id" required></label><label>Customer ID<input name="customer_id" required></label><label>Program ID<input name="program_id" required></label><label>Case ID<input name="case_id" required></label>
      <label class="wide">Contract ID<input name="contract_id"></label><label class="wide">Nomination ID<input name="nomination_id"></label>
    </div></section>
    <section class="panel"><h2>2 — Commitment / actual / exposure</h2><div class="grid">
      <label>Currency<input name="currency" maxlength="3" value="EUR" required></label><label>Forecast units<input name="forecast_units" type="number" min="0" step="any"></label><label>Committed units<input name="committed_units" type="number" min="0" step="any" required></label><label>Actual units<input name="actual_units" type="number" min="0" step="any" required></label>
      <label>Dedicated cost<input name="dedicated_cost" type="number" min="0" step="any" required></label><label>Amortization basis units<input name="amortization_basis_units" type="number" min="0" step="any" required></label><label>Mitigation<input name="mitigation" type="number" min="0" step="any" value="0"></label><label>Prior payment / recovery<input name="prior_payment" type="number" min="0" step="any" value="0"></label>
      <label>Commitment state<select name="commitment_state"><option>AMBIGUOUS</option><option>FIRM</option><option>FLEX_WINDOW</option><option>FORECAST_ONLY</option><option>NONE</option></select></label>
      <label>Exposure type<select name="exposure_type"><option>DEDICATED_CAPEX</option><option>TOOLING</option><option>NRE</option><option>LABOR</option><option>MATERIAL</option><option>OTHER</option></select></label>
      <label>Cost recovery mode<select name="cost_recovery_mode"><option>UNIT_AMORTIZED</option><option>DIRECT_UNRECOVERED</option></select></label>
      <label>Asset dedicated?<select name="asset_dedicated"><option value="true">Yes</option><option value="false">No</option></select></label>
      <label>Fully amortized?<select name="already_fully_amortized"><option value="false">No</option><option value="true">Yes</option></select></label><label>Already paid?<select name="already_paid"><option value="false">No</option><option value="true">Yes</option></select></label>
    </div></section>
    <section class="panel"><h2>3 — Integrity / contractual support</h2><div class="grid">
      <label>Customer matches evidence?<select name="customer_matches"><option value="unknown">Unknown</option><option value="true">Yes</option><option value="false">No</option></select></label>
      <label>Recovery right<select name="explicit_recovery_right"><option value="unknown">Unknown</option><option value="true">Supported</option><option value="false">Not supported</option></select></label>
      <label>Evidence supported?<select name="evidence_supported"><option value="false">No / incomplete</option><option value="true">Yes</option></select></label>
      <label>Duplicate claim?<select name="duplicate_claim"><option value="false">No</option><option value="true">Yes</option></select></label>
      <label>Program matches?<select name="program_matches"><option value="unknown">Unknown</option><option value="true">Yes</option><option value="false">No</option></select></label><label>Period matches?<select name="period_matches"><option value="unknown">Unknown</option><option value="true">Yes</option><option value="false">No</option></select></label><label>Currency matches?<select name="currency_matches"><option value="unknown">Unknown</option><option value="true">Yes</option><option value="false">No</option></select></label><label>Unit matches?<select name="unit_matches"><option value="unknown">Unknown</option><option value="true">Yes</option><option value="false">No</option></select></label>
      <label>Actuals complete?<select name="actuals_complete"><option value="unknown">Unknown</option><option value="true">Yes</option><option value="false">No</option></select></label><label>Actuals deduplicated?<select name="actuals_deduplicated"><option value="unknown">Unknown</option><option value="true">Yes</option><option value="false">No</option></select></label><label>Cancelled orders excluded?<select name="cancelled_orders_excluded"><option value="unknown">Unknown</option><option value="true">Yes</option><option value="false">No</option></select></label><label>Amortization basis verified?<select name="amortization_verified"><option value="unknown">Unknown</option><option value="true">Yes</option><option value="false">No</option></select></label>
      <label>Asset dedication verified?<select name="asset_dedication_verified"><option value="unknown">Unknown</option><option value="true">Yes</option><option value="false">No</option></select></label><label>Mitigation reviewed?<select name="mitigation_reviewed"><option value="unknown">Unknown</option><option value="true">Yes</option><option value="false">No</option></select></label><label>Prior recovery/payment reviewed?<select name="prior_recovery_reviewed"><option value="unknown">Unknown</option><option value="true">Yes</option><option value="false">No</option></select></label><label>Notice window verified?<select name="notice_window_verified"><option value="unknown">Unknown</option><option value="true">Yes — absolute deadline evidenced</option><option value="false">No</option></select></label>
      <label>Notice / deadline valid?<select name="notice_valid"><option value="unknown">Unknown</option><option value="true">Yes</option><option value="false">No / expired</option></select></label><label>Contract matches evidence?<select name="contract_matches"><option value="unknown">Unknown</option><option value="true">Yes</option><option value="false">No</option></select></label><label>Current contract?<select name="contract_current"><option value="unknown">Unknown</option><option value="true">Yes</option><option value="false">No</option></select></label><label>Amendments reviewed?<select name="amendment_reviewed"><option value="unknown">Unknown</option><option value="true">Yes</option><option value="false">No</option></select></label>
      <label>Applicable amendment matches?<select name="amendment_matches"><option value="unknown">Unknown</option><option value="true">Yes / no amendment applicable confirmed</option><option value="false">No</option></select></label>
    </div></section>
    <section class="panel"><h2>4 — Evidence / deadlines</h2><div class="grid">
      <label class="wide">Evidence refs — one per line<textarea name="evidence_refs" placeholder="contract:LTA-2026-01#12\nactuals:2026Q2"></textarea></label><label class="wide">Missing evidence — one per line<textarea name="missing_evidence" placeholder="signed amendment\ncustomer release history"></textarea></label>
      <label>Absolute notice deadline<input name="deadline" type="date"></label>
    </div></section>
    <button id="submit" type="submit">Save & assess case</button>
  </form>
  <section id="result" class="panel result" aria-live="polite">
    <h2>Assisted assessment</h2><div class="metrics">
      <div class="metric">State<b id="state" class="state">—</b></div><div class="metric">Economic exposure<b id="exposure">—</b></div><div class="metric">Net exposure<b id="net">—</b></div><div class="metric">Claimable amount<b id="claimable">—</b></div>
    </div><p class="small" id="version"></p><h2>Reasons / next actions</h2><pre id="actions"></pre><details><summary>Full truth-preserving package</summary><pre id="raw"></pre></details>
  </section>
</main>
<script>
const form=document.getElementById('case-form'), submit=document.getElementById('submit'), result=document.getElementById('result');
const tri=v=>v==='true'?true:v==='false'?false:null, bool=v=>v==='true', lines=v=>v.split('\n').map(x=>x.trim()).filter(Boolean);
form.addEventListener('submit',async e=>{e.preventDefault();submit.disabled=true;result.style.display='block';document.getElementById('actions').textContent='Assessing…';
  const d=new FormData(form), recovery={case_id:d.get('case_id'),currency:d.get('currency'),committed_units:d.get('committed_units'),actual_units:d.get('actual_units'),dedicated_cost:d.get('dedicated_cost'),amortization_basis_units:d.get('amortization_basis_units'),mitigation:d.get('mitigation')||'0',prior_payment:d.get('prior_payment')||'0',commitment_state:d.get('commitment_state'),explicit_recovery_right:tri(d.get('explicit_recovery_right')),evidence_supported:bool(d.get('evidence_supported')),notice_valid:tri(d.get('notice_valid')),customer_matches:tri(d.get('customer_matches')),program_matches:tri(d.get('program_matches')),period_matches:tri(d.get('period_matches')),currency_matches:tri(d.get('currency_matches')),unit_matches:tri(d.get('unit_matches')),actuals_complete:tri(d.get('actuals_complete')),actuals_deduplicated:tri(d.get('actuals_deduplicated')),cancelled_orders_excluded:tri(d.get('cancelled_orders_excluded')),amortization_verified:tri(d.get('amortization_verified')),asset_dedication_verified:tri(d.get('asset_dedication_verified')),mitigation_reviewed:tri(d.get('mitigation_reviewed')),prior_recovery_reviewed:tri(d.get('prior_recovery_reviewed')),notice_window_verified:tri(d.get('notice_window_verified')),contract_matches:tri(d.get('contract_matches')),contract_current:tri(d.get('contract_current')),amendment_reviewed:tri(d.get('amendment_reviewed')),amendment_matches:tri(d.get('amendment_matches')),asset_dedicated:bool(d.get('asset_dedicated')),already_fully_amortized:bool(d.get('already_fully_amortized')),already_paid:bool(d.get('already_paid')),exposure_type:d.get('exposure_type'),cost_recovery_mode:d.get('cost_recovery_mode'),duplicate_claim:bool(d.get('duplicate_claim'))};
  const payload={company_id:d.get('company_id'),customer_id:d.get('customer_id'),program_id:d.get('program_id'),contract_id:d.get('contract_id')||null,nomination_id:d.get('nomination_id')||null,forecast_units:d.get('forecast_units')||null,recovery_case:recovery,evidence_refs:lines(d.get('evidence_refs')),missing_evidence:lines(d.get('missing_evidence')),deadline:d.get('deadline')||null};
  try{const r=await fetch('/api/capacity/cases',{method:'POST',headers:{'Content-Type':'application/json','X-Capacity-Intent':'create-case'},body:JSON.stringify(payload)});const body=await r.json();if(!r.ok)throw new Error(body.detail||body.error||('HTTP '+r.status));
    document.getElementById('state').textContent=body.result.recoverability_state;document.getElementById('exposure').textContent=body.result.currency+' '+body.result.economic_exposure;document.getElementById('net').textContent=body.result.currency+' '+body.result.net_exposure;document.getElementById('claimable').textContent=body.result.currency+' '+body.result.claimable_amount;document.getElementById('version').textContent='Engine '+body.result.engine_version+' · not verified recovery · not payment';document.getElementById('actions').textContent=[...(body.result.reasons||[]),...(body.recovery_package.next_actions||[])].join('\n');document.getElementById('raw').textContent=JSON.stringify(body,null,2);
  }catch(err){document.getElementById('state').textContent='ERROR';document.getElementById('exposure').textContent='—';document.getElementById('net').textContent='—';document.getElementById('claimable').textContent='—';document.getElementById('actions').textContent=err.message;document.getElementById('raw').textContent='';}finally{submit.disabled=false;}
});
</script>
</body></html>'''
