"use strict";

const findingFields = ["review_finding_id", "action_finding_id", "resolve_finding_id"];

function node(id) {
  return document.getElementById(id);
}

function setFinding(id, currency) {
  findingFields.forEach((key) => {
    const target = node(key);
    if (target) target.value = id || "";
  });
  const currencyField = node("currency");
  if (currency && currencyField) currencyField.value = String(currency).toUpperCase();
}

function render(target, response, body) {
  const targetNode = node(target);
  if (!targetNode) return;
  targetNode.className = "result" + (response.ok ? "" : " error");
  targetNode.replaceChildren();
  const heading = document.createElement("strong");
  heading.textContent = response.ok ? `HTTP ${response.status} — ${body.state || "OK"}` : `HTTP ${response.status} — ${body.error || "request_failed"}`;
  const detail = document.createElement("pre");
  detail.textContent = JSON.stringify(body, null, 2);
  targetNode.append(heading, detail);
}

async function loadDetail(id) {
  const findingId = String(id || "").trim();
  if (!findingId) {
    const target = node("detail-result");
    if (target) {
      target.className = "result error";
      target.textContent = "Select a finding before loading its dossier.";
    }
    return null;
  }
  return send(`/findings/${encodeURIComponent(findingId)}`, {method: "GET"}, "detail-result");
}

function renderQueue(body) {
  const list = node("queue-list");
  if (!list) return;
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
    const targetNode = node(target);
    if (targetNode) {
      targetNode.className = "result error";
      targetNode.textContent = `Network or parsing error: ${error.message}`;
    }
    return null;
  }
}

async function loadQueue() {
  const result = await send("/findings", {method: "GET"}, "queue-result");
  if (result && result.response.ok) renderQueue(result.body);
  else {
    const list = node("queue-list");
    if (list) list.replaceChildren();
  }
}

function jsonRequest(payload) {
  return {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(payload)};
}

function installAmendmentControl() {
  const grid = document.querySelector("#analyze-form .form-grid");
  if (!grid || node("amend_finding_id")) return;
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
  note.textContent = "An amendment keeps the same recovery identity, creates a new revision and requires fresh independent review. In secure mode this form carries references/economics only; real documentary originals must use authorized secure capture.";
  field.append(label, input, note);
  grid.prepend(field);
}

installAmendmentControl();

const refreshQueue = node("refresh-queue");
if (refreshQueue) refreshQueue.addEventListener("click", loadQueue);

const noticeDue = node("notice_due");
if (noticeDue) noticeDue.addEventListener("change", (event) => {
  const noDeadline = node("notice_deadline_not_applicable");
  if (event.target.value && noDeadline) noDeadline.checked = false;
});

const noNoticeDeadline = node("notice_deadline_not_applicable");
if (noNoticeDeadline) noNoticeDeadline.addEventListener("change", (event) => {
  const due = node("notice_due");
  if (event.target.checked && due) due.value = "";
});

const analyzeForm = node("analyze-form");
if (analyzeForm) analyzeForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const payload = Object.fromEntries(new FormData(event.currentTarget).entries());
  const amendFindingId = String(payload.amend_finding_id || "").trim();
  delete payload.amend_finding_id;
  ["avoided_cost", "resale_reuse", "third_party_recovery", "prior_payment", "other_mitigation"].forEach((key) => { payload[key] = payload[key] || "0"; });
  payload.currency = String(payload.currency || "").trim().toUpperCase();
  payload.notice_deadline_not_applicable = Boolean(noNoticeDeadline && noNoticeDeadline.checked);
  if (!payload.notice_due) delete payload.notice_due;
  payload.missing_evidence = (payload.missing_evidence || "").split(",").map((value) => value.trim()).filter(Boolean);
  const path = amendFindingId ? `/findings/${encodeURIComponent(amendFindingId)}/amend` : "/analyze";
  const result = await send(path, jsonRequest(payload), "analyze-result");
  if (result && result.response.ok) {
    setFinding(result.body.finding_id, result.body.currency);
    await loadDetail(result.body.finding_id);
  }
});

const reviewForm = node("review-form");
if (reviewForm) reviewForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const approved = event.submitter.dataset.approved === "true";
  const finding = node("review_finding_id");
  const reason = node("review_reason");
  if (!finding || !reason) return;
  const id = finding.value;
  const result = await send(`/findings/${encodeURIComponent(id)}/review`, jsonRequest({approved, reason: reason.value}), "review-result");
  if (result && result.response.ok) {
    await loadDetail(id);
    await loadQueue();
  }
});

const actionForm = node("action-form");
if (actionForm) actionForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const finding = node("action_finding_id");
  if (!finding) return;
  const id = finding.value;
  const result = await send(`/findings/${encodeURIComponent(id)}/action`, {method: "POST"}, "action-result");
  if (result && result.response.ok) {
    await loadDetail(id);
    await loadQueue();
  }
});

const resolveForm = node("resolve-form");
if (resolveForm) resolveForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const finding = node("resolve_finding_id");
  const outcome = node("outcome_id");
  const amount = node("recovered_amount");
  const currency = node("currency");
  const evidenceRef = node("evidence_ref");
  const evidenceContent = node("evidence_content");
  const finalCumulative = node("final_cumulative");
  if (!finding || !outcome || !amount || !currency || !evidenceRef || !evidenceContent || !finalCumulative) return;
  const id = finding.value;
  const payload = {
    outcome_id: outcome.value,
    recovered_amount: amount.value,
    currency: currency.value.trim().toUpperCase(),
    evidence_ref: evidenceRef.value,
    evidence_content: evidenceContent.value,
    final_cumulative: finalCumulative.checked,
  };
  const result = await send(`/findings/${encodeURIComponent(id)}/resolve`, jsonRequest(payload), "resolve-result");
  if (result && result.response.ok) {
    finalCumulative.checked = false;
    await loadDetail(id);
    await loadQueue();
  }
});
