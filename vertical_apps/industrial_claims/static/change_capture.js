"use strict";

const shell = document.querySelector(".capture-shell");
const form = document.getElementById("change-summary-form");
const lateForm = document.getElementById("late-supplement-form");
const countdown = document.getElementById("capture-countdown");
const stateNode = document.getElementById("capture-state");
const resultNode = document.getElementById("capture-result");
const lateResultNode = document.getElementById("late-supplement-result");
const trustNode = document.getElementById("capture-time-trust");
const digestNode = document.getElementById("capture-sheet-digest");
const downloadNode = document.getElementById("change-sheet-download");
const closesAt = shell ? new Date(shell.dataset.closesAt) : null;
const findingId = shell ? String(shell.dataset.findingId || "") : "";

function setClosedUi() {
  document.querySelectorAll(".open-only").forEach((node) => { node.hidden = true; });
  document.querySelectorAll(".closed-only").forEach((node) => { node.hidden = false; });
  if (stateNode) {
    stateNode.textContent = "CLOSED";
    stateNode.className = "capture-state closed";
  }
  if (countdown) countdown.textContent = "Closed";
  if (form) Array.from(form.elements).forEach((element) => { element.disabled = true; });
}

function renderRemaining() {
  if (!closesAt || Number.isNaN(closesAt.getTime())) {
    if (countdown) countdown.textContent = "Unavailable";
    return;
  }
  const remainingMs = closesAt.getTime() - Date.now();
  if (remainingMs < 0) {
    setClosedUi();
    return;
  }
  const totalSeconds = Math.floor(remainingMs / 1000);
  const days = Math.floor(totalSeconds / 86400);
  const hours = Math.floor((totalSeconds % 86400) / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  if (countdown) {
    countdown.textContent = days > 0
      ? `${days}d ${hours}h ${minutes}m`
      : `${hours}h ${minutes}m ${seconds}s`;
  }
}

function renderTrust(trust) {
  if (!trust || typeof trust !== "object") return;
  if (digestNode && trust.current_snapshot_sha256) digestNode.textContent = trust.current_snapshot_sha256;
  if (!trustNode) return;
  if (trust.current_snapshot_externally_timestamped === true) {
    const current = trust.current_timestamp || {};
    const provider = current.provider ? ` by ${current.provider}` : "";
    const issued = current.issued_at ? ` at ${current.issued_at}` : "";
    trustNode.className = "trust-verified";
    trustNode.textContent = `Independent timestamp: VERIFIED${provider}${issued} for this exact snapshot.`;
    return;
  }
  trustNode.className = "trust-pending";
  trustNode.textContent = trust.stale_attestation_exists_for_older_snapshot
    ? "Independent qualified timestamp: NOT VERIFIED for this current snapshot. An older version has time evidence, but it does not transfer after the digest changed."
    : "Independent qualified timestamp: NOT VERIFIED for this exact snapshot. CausLedger does not label internal server time as qualified evidence.";
}

async function refreshTrust() {
  if (!findingId) return;
  try {
    const response = await fetch(`/findings/${encodeURIComponent(findingId)}/change-sheet/trust`, {method: "GET"});
    const body = await response.json();
    if (response.ok) renderTrust(body);
  } catch (_error) {
    // Trust state remains visibly unverified if a refresh cannot be completed.
  }
}

async function postFact(factType, factText, sourceRef) {
  const response = await fetch(`/findings/${encodeURIComponent(findingId)}/change-facts`, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({
      confirm_factual_entry: true,
      fact_type: factType,
      fact_text: factText,
      source_ref: sourceRef || null,
    }),
  });
  const body = await response.json();
  if (!response.ok) throw new Error(body.message || body.error || "Factual record could not be saved.");
  if (body.capture && body.capture.snapshot_time_trust) renderTrust(body.capture.snapshot_time_trust);
  return body;
}

if (form) {
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const requestedChange = document.getElementById("requested_change").value.trim();
    const requestedAt = document.getElementById("declared_requested_at").value.trim();
    const sourceRef = document.getElementById("source_ref").value.trim();
    const submit = form.querySelector("button[type='submit']");
    if (!requestedChange) return;
    submit.disabled = true;
    resultNode.className = "result";
    resultNode.textContent = "Saving append-only factual record…";
    try {
      const summary = await postFact("REQUESTED_CHANGE", requestedChange, sourceRef);
      let latest = summary;
      if (requestedAt) latest = await postFact("CHANGE_REQUESTED_AT", requestedAt, sourceRef);
      const recordedAt = latest.fact_receipt ? latest.fact_receipt.recorded_at : "recorded";
      resultNode.textContent = `Saved at ${recordedAt}. The sheet digest has been refreshed. Download this version and keep it with the project record.`;
      await refreshTrust();
    } catch (error) {
      resultNode.className = "result error";
      resultNode.textContent = error.message;
      if (String(error.message).includes("window is closed")) setClosedUi();
    } finally {
      submit.disabled = false;
    }
  });
}

if (lateForm) {
  lateForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const submit = lateForm.querySelector("button[type='submit']");
    submit.disabled = true;
    lateResultNode.className = "result";
    lateResultNode.textContent = "Recording separate late supplement…";
    const payload = {
      confirm_late_supplement: true,
      fact_text: document.getElementById("late_fact_text").value.trim(),
      reason_for_late_entry: document.getElementById("late_reason").value.trim(),
      declared_event_at: document.getElementById("late_declared_event_at").value.trim() || null,
      source_ref: document.getElementById("late_source_ref").value.trim() || null,
    };
    try {
      const response = await fetch(`/findings/${encodeURIComponent(findingId)}/late-supplements`, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(payload),
      });
      const body = await response.json();
      if (!response.ok) throw new Error(body.message || body.error || "Late supplement could not be recorded.");
      const item = body.supplement || {};
      lateResultNode.textContent = `Recorded separately at ${item.recorded_at || "server time"}. Classification: LATE_SUPPLEMENT. The original change sheet was not rewritten.`;
      lateForm.reset();
    } catch (error) {
      lateResultNode.className = "result error";
      lateResultNode.textContent = error.message;
    } finally {
      submit.disabled = false;
    }
  });
}

if (downloadNode) {
  downloadNode.addEventListener("click", () => {
    if (trustNode) {
      trustNode.className = "trust-pending";
      trustNode.textContent = "Requesting external timestamp status for the exported snapshot…";
    }
    window.setTimeout(refreshTrust, 1200);
    window.setTimeout(refreshTrust, 3000);
  });
}

renderRemaining();
refreshTrust();
setInterval(renderRemaining, 1000);