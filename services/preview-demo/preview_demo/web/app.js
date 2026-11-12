"use strict";

const el = (id) => document.getElementById(id);
const operator = location.pathname === "/operator";
const sample = location.pathname === "/preview";
const storageKey = operator ? "preview.operator" : "preview.guest";
const example = "Deploy version 2 for 30 minutes.";
const labels = {
  awaiting_approval: "Waiting for approval",
  planning: "Planning",
  starting: "Starting",
  verifying: "Checking health",
  ready: "Ready to test",
  removed: "Removed",
  expired: "Expired",
};
let token = sessionStorage.getItem(storageKey);
let job = null;
let poll = null;
let busy = false;
let refreshing = false;

function message(text = "") {
  el("message").textContent = text;
  el("message").hidden = !text;
}

async function api(path, body, method = "GET") {
  const headers = token ? {Authorization: `Bearer ${token}`} : {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  let response;
  try {
    response = await fetch(path, {
      method, headers, body: body === undefined ? undefined : JSON.stringify(body),
      signal: AbortSignal.timeout(path === "/api/requests" ? 25000 : 5000),
    });
  } catch {
    throw new Error("The local server did not respond. Make sure the rehearsal is running.");
  }
  const data = await response.json().catch(() => {
    throw new Error(`The local server returned an unexpected response (HTTP ${response.status}).`);
  });
  if (!response.ok) throw Object.assign(new Error(data.detail), {status: response.status});
  return data;
}

function render() {
  const active = job && !["expired", "removed"].includes(job.phase);
  const ready = job?.phase === "ready";
  el("operator").hidden = !operator;
  el("guest").hidden = operator || sample;
  el("status").hidden = sample || (!operator && !job);
  el("sample").hidden = !sample || !ready;
  el("test-v2").hidden = job?.spec.version !== 2;
  el("result-card-2").hidden = job?.spec.version !== 2;
  el("submit").disabled = Boolean(active);
  el("status-title").textContent = operator ? "Current request" : "2. Follow your request";
  el("phase").textContent = labels[job?.phase] ?? "Idle";
  el("spec").textContent = job
    ? `Validated spec: version ${job.spec.version} · ${job.spec.minutes} minutes`
    : "Waiting for a tester to submit a request.";
  el("approve").hidden = !operator || job?.phase !== "awaiting_approval";
  el("destroy").hidden = !operator || !active;
  el("open").hidden = operator || !ready;
  el("events").replaceChildren(...(job?.events ?? []).map((event) => {
    const item = document.createElement("li");
    const time = new Date(event.at).toLocaleTimeString();
    item.textContent = `${time} · ${event.message}`;
    return item;
  }));
}

async function refresh() {
  if (refreshing) return;
  refreshing = true;
  try {
    const state = await api("/api/status");
    if (state.role !== (operator ? "owner" : "guest")) {
      throw Object.assign(new Error("Open the link for your role."), {status: 401});
    }
    const changed = job?.id !== state.deployment?.id || job?.phase !== state.deployment?.phase;
    job = state.deployment;
    if (changed) render();
    if (sample && changed && job?.phase !== "ready") location.replace("/");
  } catch (error) {
    if (error.status === 401) {
      clearInterval(poll);
      sessionStorage.removeItem(storageKey);
      for (const id of ["operator", "guest", "status", "sample"]) el(id).hidden = true;
    }
    message(error.message);
  } finally {
    refreshing = false;
  }
}

async function action(button, perform) {
  if (busy) return;
  busy = true;
  button.disabled = true;
  message();
  try {
    await perform();
    await refresh();
  } catch (error) {
    message(error.message);
  } finally {
    busy = false;
    button.disabled = false;
    render();
  }
}

el("example").addEventListener("click", () => {
  el("request").value = example;
  el("request").focus();
});
el("invite").addEventListener("click", (event) => action(event.currentTarget, async () => {
  const data = await api("/api/invites", undefined, "POST");
  el("invite-url").value = `${location.origin}/#${data.invite}`;
  el("share").hidden = false;
}));
el("copy").addEventListener("click", async () => {
  el("invite-url").select();
  try {
    await navigator.clipboard.writeText(el("invite-url").value);
    message("Tester link copied.");
  } catch {
    message("Tester link selected. Copy it with your browser's copy command.");
  }
});
el("request-form").addEventListener("submit", (event) => {
  event.preventDefault();
  return action(el("submit"), async () => {
    job = await api("/api/requests", {request: el("request").value}, "POST");
  });
});
for (const id of ["approve", "destroy"]) {
  el(id).addEventListener("click", (event) => action(event.currentTarget, async () => {
    job = await api(`/api/requests/${job.id}/${id}`, undefined, "POST");
  }));
}
el("sample-form").addEventListener("submit", (event) => {
  event.preventDefault();
  const button = event.submitter;
  if (!button) return;
  return action(button, async () => {
    const version = button.value;
    const input = el("email");
    input.disabled = true;
    try {
      const data = await api(`/api/sample/${version}`, {email: input.value}, "POST");
      el(`result-${version}`).textContent = data.accepted
        ? "Accepted the input."
        : "Rejected the input. Enter a valid email address.";
    } finally {
      input.disabled = false;
    }
  });
});
el("email").addEventListener("input", () => {
  for (const version of [1, 2]) el(`result-${version}`).textContent = "Waiting for a test.";
});

async function start() {
  try {
    const linkToken = location.hash.slice(1);
    if (linkToken) {
      history.replaceState(null, "", location.pathname);
      token = operator ? linkToken : (await api("/api/join", {invite: linkToken}, "POST")).session;
      sessionStorage.setItem(storageKey, token);
    }
    if (!token) throw new Error("Ask the operator for a single-use tester link.");
    const state = await api("/api/status");
    el("mode").textContent = `Local deployment simulation · Intent: ${state.intent}`;
    if (state.role !== (operator ? "owner" : "guest")) throw new Error("Open the link for your role.");
    job = state.deployment;
    if (sample && job?.phase !== "ready") {
      location.replace("/");
      return;
    }
    render();
    poll = setInterval(() => { if (!busy) void refresh(); }, 1000);
  } catch (error) {
    message(error.message);
  }
}

void start();
