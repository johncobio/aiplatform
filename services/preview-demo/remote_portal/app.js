"use strict";
const byId = (id) => document.getElementById(id);
const fragment = location.hash.slice(1);
if (fragment) {
  history.replaceState(null, "", location.pathname);
  sessionStorage.setItem("preview-invite", fragment);
}
const token = sessionStorage.getItem("preview-invite");
const labels = {
  invited: "Your invite is ready.",
  demo_ready: "Your AWS demo is ready. You have 15 minutes from first opening this link.",
  requested: "Request sent. Waiting for the operator.",
  planned: "Deployment planned. Waiting for operator approval.",
  applying: "Terraform is provisioning the preview.",
  available: "AWS issued an endpoint. Open it to test the preview.",
  expired: "This preview window has ended.",
  failed: "Deployment failed. Ask the operator for details.",
  rejected: "The operator could not turn this into a supported preview.",
  closed: "This request is closed.",
};
let state;
let busy = false;

async function refresh(method = "GET", body) {
  if (!token) {
    byId("status").textContent = "Open your private invite link to get started.";
    return;
  }
  if (busy) return;
  busy = true;
  try {
    const response = await fetch("/api/request", {
      method,
      headers: {Authorization: `Bearer ${token}`, "Content-Type": "application/json"},
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: AbortSignal.timeout(7000),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error ?? "Request unavailable.");
    state = result.status;
    byId("status").textContent = labels[state];
    byId("request-form").hidden = state !== "invited";
    byId("demo-form").hidden = state !== "demo_ready";
    byId("spec").hidden = !result.version;
    byId("spec").textContent = result.version
      ? `Reviewed spec: version ${result.version} for ${result.minutes} minutes.` : "";
    byId("hint").hidden = !result.endpoint;
    byId("open").hidden = !result.endpoint;
    byId("open").href = result.endpoint ?? "#";
  } catch (error) {
    byId("status").textContent = error.message;
    byId("open").hidden = true;
    byId("hint").hidden = true;
  } finally {
    busy = false;
  }
}
byId("request-form").addEventListener("submit", (event) => {
  event.preventDefault();
  void refresh("POST", {request: byId("request").value});
});
byId("demo-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = byId("compare");
  const output = byId("demo-result");
  button.disabled = true;
  output.textContent = "Checking both versions…";
  try {
    const response = await fetch("/api/demo", {
      method: "POST",
      headers: {Authorization: `Bearer ${token}`, "Content-Type": "application/json"},
      body: JSON.stringify({email: byId("demo-email").value}),
      signal: AbortSignal.timeout(12000),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error ?? "Demo unavailable.");
    output.textContent = `Version 1: ${result.version1 ? "accepted" : "rejected"}. `
      + `Version 2: ${result.version2 ? "accepted" : "rejected"}.`;
  } catch (error) {
    output.textContent = error.message;
  } finally {
    button.disabled = false;
  }
});
void refresh();
setInterval(() => {
  if (!document.hidden && state !== "invited" && !["closed", "expired", "rejected"].includes(state)) {
    void refresh();
  }
}, 5000);
