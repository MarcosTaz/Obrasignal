"use strict";

const shell = document.querySelector(".capture-shell");
const form = document.getElementById("change-summary-form");
const countdown = document.getElementById("capture-countdown");
const stateNode = document.getElementById("capture-state");
const resultNode = document.getElementById("capture-result");
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
      resultNode.textContent = `Saved at ${recordedAt}. Download the change sheet now and keep it with the project record.`;
    } catch (error) {
      resultNode.className = "result error";
      resultNode.textContent = error.message;
      if (String(error.message).includes("window is closed")) setClosedUi();
    } finally {
      submit.disabled = false;
    }
  });
}

renderRemaining();
setInterval(renderRemaining, 1000);
