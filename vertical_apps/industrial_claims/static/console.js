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
  heading.textContent = response.ok
    ? `HTTP ${response.status} — ${body.state || "OK"}`
    : `HTTP ${response.status} — ${body.error || "request_failed"}`;

  const detail = document.createElement("pre");
  detail.textContent = JSON.stringify(body, null, 2);
  node.append(heading, detail);
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
    item.addEventListener("click", () => setFinding(String(finding.finding_id || ""), finding.currency_unit));
    list.append(item);
  });

  if (!findings.length) {
    const empty = document.createElement("p");
    empty.className = "note";
    empty.textContent = "No actionable findings for this verified role and tenant.";
    list.append(empty);
  }
}

async function send(path, options, target) {
  try {
    const response = await fetch(path, options);
    const contentType = response.headers.get("content-type") || "";
    const body = contentType.includes("application/json")
      ? await response.json()
      : {error: "unexpected_response", message: "Server returned a non-JSON response."};
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
  if (result && result.response.ok) {
    renderQueue(result.body);
  } else {
    document.getElementById("queue-list").replaceChildren();
  }
}

function jsonRequest(payload) {
  return {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(payload),
  };
}

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
  ["avoided_cost", "resale_reuse", "third_party_recovery", "prior_payment", "other_mitigation"].forEach((key) => {
    payload[key] = payload[key] || "0";
  });
  payload.currency = String(payload.currency || "").trim().toUpperCase();
  payload.notice_deadline_not_applicable = document.getElementById("notice_deadline_not_applicable").checked;
  if (!payload.notice_due) delete payload.notice_due;
  payload.missing_evidence = (payload.missing_evidence || "")
    .split(",")
    .map((value) => value.trim())
    .filter(Boolean);

  const result = await send("/analyze", jsonRequest(payload), "analyze-result");
  if (result && result.response.ok) setFinding(result.body.finding_id, result.body.currency);
});

document.getElementById("review-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const approved = event.submitter.dataset.approved === "true";
  const id = document.getElementById("review_finding_id").value;
  const result = await send(
    `/findings/${encodeURIComponent(id)}/review`,
    jsonRequest({approved, reason: document.getElementById("review_reason").value}),
    "review-result",
  );
  if (result && result.response.ok) await loadQueue();
});

document.getElementById("action-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const id = document.getElementById("action_finding_id").value;
  const result = await send(`/findings/${encodeURIComponent(id)}/action`, {method: "POST"}, "action-result");
  if (result && result.response.ok) await loadQueue();
});

document.getElementById("resolve-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const id = document.getElementById("resolve_finding_id").value;
  const payload = {
    outcome_id: document.getElementById("outcome_id").value,
    recovered_amount: document.getElementById("recovered_amount").value,
    currency: document.getElementById("currency").value.trim().toUpperCase(),
    evidence_ref: document.getElementById("evidence_ref").value,
  };
  const result = await send(`/findings/${encodeURIComponent(id)}/resolve`, jsonRequest(payload), "resolve-result");
  if (result && result.response.ok) await loadQueue();
});
