"use strict";

const findingFields = ["review_finding_id", "action_finding_id", "resolve_finding_id"];

function setFinding(id, currency) {
  findingFields.forEach((key) => {
    document.getElementById(key).value = id || "";
  });
  if (currency) document.getElementById("currency").value = String(currency).toUpperCase();
}

function render(target, response, body) {
  const node = document.getElementById(target);
  node.className = "result" + (response.ok ? "" : " error");
  node.replaceChildren();
  const heading = document.createElement("strong");
  heading.textContent = response.ok ? `HTTP ${response.status} — ${body.state || "OK"}` : `HTTP ${response.status} — ${body.error || "request_failed"}`;
  const detail = document.createElement("pre");
  detail.textContent = JSON.stringify(body, null, 2);
  node.append(heading, detail);
}

async function loadDetail(id) {
  const findingId = String(id || "").trim();
  if (!findingId) {
    const node = document.getElementById("detail-result");
    node.className = "result error";
    node.textContent = "Select a finding before loading its dossier.";
    return null;
  }
  return send(`/findings/${encodeURIComponent(findingId)}`, {method: "GET"}, "detail-result");
}

function renderQueue(body) {
  const list = document.getElementById("queue-list");
  list.replaceChildren();
  const findings = Array.isArray(body.findings) ? body.findings : [];
  findings.forEach((finding) => {
    const item = document.createElement("button");
    item.type = "button";
    item.className = "queue-item";
    const title = document.createElement("strong");
    title.textContent = String(finding.state || "UNKNOWN");
    const amount = document.createElement("span");
    amount.textContent = `Net potential: ${String(finding.net_potential || "UNKNOWN")} ${String(finding.currency_unit || "")}`.trim();
    const identifier = document.createElement("code");
    identifier.textContent = String(finding.finding_id || "");
    const provenance = document.createElement("small");
    provenance.textContent = `Created by ${String(finding.creator_actor || "UNKNOWN")} — ${String(finding.created_at || "UNKNOWN")}`;
    item.append(title, amount, identifier, provenance);
    item.addEventListener("click", async () => {
      const id = String(finding.finding_id || "");
      setFinding(id, finding.currency_unit);
      await loadDetail(id);
    });
    list.append(item);
  });
  if (!findings.length) {
    const empty = document.createElement("p");
    empty.className = "note";
    empty.textContent = "No workflow findings for this verified role and tenant.";
    list.append(empty);
  }
}

async function send(path, options, target) {
  try {
    const response = await fetch(path, options);
    const contentType = response.headers.get("content-type") || "";
    const body = contentType.includes("application/json") ? await response.json() : {error: "unexpected_response", message: "Server returned a non-JSON response."};
    render(target, response, body);
    return {response, body};
  } catch (error) {
    const node = document.getElementById(target);
    node.className = "result error";
    node.textContent = `Network or parsing error: ${error.message}`;
    return null;
  }
}

async function loadQueue() {
  const result = await send("/findings", {method: "GET"}, "queue-result");
  if (result && result.response.ok) renderQueue(result.body);
  else document.getElementById("queue-list").replaceChildren();
}

function jsonRequest(payload) {
  return {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(payload)};
}

function installAmendmentControl() {
  const grid = document.querySelector("#analyze-form .form-grid");
  if (!grid || document.getElementById("amend_finding_id")) return;
  const field = document.createElement("div");
  field.className = "field full";
  const label = document.createElement("label");
  label.htmlFor = "amend_finding_id";
  label.textContent = "Current finding ID to amend — optional";
  const input = document.createElement("input");
  input.id = "amend_finding_id";
  input.name = "amend_finding_id";
  input.maxLength = 2048;
  input.autocomplete = "off";
  input.placeholder = "Leave blank for a new recovery; enter the current finding ID for a corrected revision.";
  const note = document.createElement("small");
  note.textContent = "An amendment keeps the same recovery identity, creates a new revision and requires fresh independent review. Supply the full corrected documentary reconstruction because raw documents are not reloaded from storage.";
  field.append(label, input, note);
  grid.prepend(field);
}

installAmendmentControl();

document.getElementById("refresh-queue").addEventListener("click", loadQueue);
document.getElementById("notice_due").addEventListener("change", (event) => {
  if (event.target.value) document.getElementById("notice_deadline_not_applicable").checked = false;
});
document.getElementById("notice_deadline_not_applicable").addEventListener("change", (event) => {
  if (event.target.checked) document.getElementById("notice_due").value = "";
});

document.getElementById("analyze-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const payload = Object.fromEntries(new FormData(event.currentTarget).entries());
  const amendFindingId = String(payload.amend_finding_id || "").trim();
  delete payload.amend_finding_id;
  ["avoided_cost", "resale_reuse", "third_party_recovery", "prior_payment", "other_mitigation"].forEach((key) => { payload[key] = payload[key] || "0"; });
  payload.currency = String(payload.currency || "").trim().toUpperCase();
  payload.notice_deadline_not_applicable = document.getElementById("notice_deadline_not_applicable").checked;
  if (!payload.notice_due) delete payload.notice_due;
  payload.missing_evidence = (payload.missing_evidence || "").split(",").map((value) => value.trim()).filter(Boolean);
  const path = amendFindingId ? `/findings/${encodeURIComponent(amendFindingId)}/amend` : "/analyze";
  const result = await send(path, jsonRequest(payload), "analyze-result");
  if (result && result.response.ok) {
    setFinding(result.body.finding_id, result.body.currency);
    await loadDetail(result.body.finding_id);
  }
});

document.getElementById("review-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const approved = event.submitter.dataset.approved === "true";
  const id = document.getElementById("review_finding_id").value;
  const result = await send(`/findings/${encodeURIComponent(id)}/review`, jsonRequest({approved, reason: document.getElementById("review_reason").value}), "review-result");
  if (result && result.response.ok) {
    await loadDetail(id);
    await loadQueue();
  }
});

document.getElementById("action-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const id = document.getElementById("action_finding_id").value;
  const result = await send(`/findings/${encodeURIComponent(id)}/action`, {method: "POST"}, "action-result");
  if (result && result.response.ok) {
    await loadDetail(id);
    await loadQueue();
  }
});

document.getElementById("resolve-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const id = document.getElementById("resolve_finding_id").value;
  const payload = {
    outcome_id: document.getElementById("outcome_id").value,
    recovered_amount: document.getElementById("recovered_amount").value,
    currency: document.getElementById("currency").value.trim().toUpperCase(),
    evidence_ref: document.getElementById("evidence_ref").value,
    evidence_content: document.getElementById("evidence_content").value,
    final_cumulative: document.getElementById("final_cumulative").checked,
  };
  const result = await send(`/findings/${encodeURIComponent(id)}/resolve`, jsonRequest(payload), "resolve-result");
  if (result && result.response.ok) {
    document.getElementById("final_cumulative").checked = false;
    await loadDetail(id);
    await loadQueue();
  }
});
