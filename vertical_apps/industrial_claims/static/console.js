"use strict";

const findingFields = ["review_finding_id", "action_finding_id", "resolve_finding_id"];

function setFinding(id) {
  findingFields.forEach((key) => {
    document.getElementById(key).value = id || "";
  });
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

function jsonRequest(payload) {
  return {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(payload),
  };
}

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
  payload.notice_deadline_not_applicable = document.getElementById("notice_deadline_not_applicable").checked;
  if (!payload.notice_due) delete payload.notice_due;
  payload.missing_evidence = (payload.missing_evidence || "")
    .split(",")
    .map((value) => value.trim())
    .filter(Boolean);

  const result = await send("/analyze", jsonRequest(payload), "analyze-result");
  if (result && result.response.ok) setFinding(result.body.finding_id);
});

document.getElementById("review-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const approved = event.submitter.dataset.approved === "true";
  const id = document.getElementById("review_finding_id").value;
  await send(
    `/findings/${encodeURIComponent(id)}/review`,
    jsonRequest({approved, reason: document.getElementById("review_reason").value}),
    "review-result",
  );
});

document.getElementById("action-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const id = document.getElementById("action_finding_id").value;
  await send(`/findings/${encodeURIComponent(id)}/action`, {method: "POST"}, "action-result");
});

document.getElementById("resolve-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const id = document.getElementById("resolve_finding_id").value;
  const payload = {
    outcome_id: document.getElementById("outcome_id").value,
    recovered_amount: document.getElementById("recovered_amount").value,
    currency: document.getElementById("currency").value,
    evidence_ref: document.getElementById("evidence_ref").value,
  };
  await send(`/findings/${encodeURIComponent(id)}/resolve`, jsonRequest(payload), "resolve-result");
});
