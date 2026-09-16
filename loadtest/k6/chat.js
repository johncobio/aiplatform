// k6 load test for the OpenAI-compatible chat endpoint.
//
//   k6 run -e BASE_URL=http://llm-service.staging.127.0.0.1.nip.io \
//          -e SCENARIO=steady -e VUS=2 -e DURATION=2m loadtest/k6/chat.js
//
// Scenarios: smoke (1 VU, 30s), steady (VUS for DURATION), ramp (0→VUS→0),
// step (1→2→4 VUs, STEP_DURATION each). Every request is a short chat
// completion (MAX_TOKENS) so throughput reflects generation, not prompt size.

import http from "k6/http";
import { check } from "k6";
import { Counter, Trend } from "k6/metrics";

const BASE_URL = __ENV.BASE_URL || "http://llm-service.staging.127.0.0.1.nip.io";
const SCENARIO = __ENV.SCENARIO || "smoke";
const VUS = Number(__ENV.VUS || 2);
const DURATION = __ENV.DURATION || "2m";
const STEP_DURATION = __ENV.STEP_DURATION || "2m";
const MAX_TOKENS = Number(__ENV.MAX_TOKENS || 32);

const completionTokens = new Counter("llm_completion_tokens");
const tokensPerSecond = new Trend("llm_tokens_per_second");
const serverTime = new Trend("llm_server_duration", true);

const PROMPTS = [
  "Explain GitOps in one sentence.",
  "What is a Kubernetes HorizontalPodAutoscaler?",
  "Give one reason to use Terraform modules.",
  "Describe a canary deployment briefly.",
  "What does an SRE error budget mean?",
  "Name two Prometheus metric types.",
];

const scenarios = {
  smoke: { executor: "constant-vus", vus: 1, duration: "30s" },
  steady: { executor: "constant-vus", vus: VUS, duration: DURATION },
  ramp: {
    executor: "ramping-vus",
    startVUs: 0,
    stages: [
      { duration: "1m", target: VUS },
      { duration: DURATION, target: VUS },
      { duration: "30s", target: 0 },
    ],
  },
  step: {
    executor: "ramping-vus",
    startVUs: 1,
    stages: [
      { duration: STEP_DURATION, target: 1 },
      { duration: STEP_DURATION, target: 2 },
      { duration: STEP_DURATION, target: 4 },
    ],
  },
};

export const options = {
  scenarios: { [SCENARIO]: scenarios[SCENARIO] },
  thresholds: {
    http_req_failed: ["rate<0.01"],
    checks: ["rate>0.99"],
  },
  summaryTrendStats: ["avg", "min", "med", "p(90)", "p(95)", "p(99)", "max"],
};

export default function () {
  const prompt = PROMPTS[(__VU + __ITER) % PROMPTS.length];
  const body = JSON.stringify({
    messages: [{ role: "user", content: prompt }],
    max_tokens: MAX_TOKENS,
    temperature: 0.2,
  });
  const res = http.post(`${BASE_URL}/v1/chat/completions`, body, {
    headers: { "Content-Type": "application/json" },
    timeout: "120s",
    tags: { name: "chat_completions" },
  });
  const ok = check(res, {
    "status 200": (r) => r.status === 200,
    "has content": (r) => r.status === 200 && r.json("choices.0.message.content") !== undefined,
  });
  if (ok) {
    const tokens = res.json("usage.completion_tokens");
    completionTokens.add(tokens);
    tokensPerSecond.add(tokens / (res.timings.duration / 1000));
    serverTime.add(res.timings.duration);
  }
}

export function handleSummary(data) {
  const out = __ENV.SUMMARY || `loadtest/results/${SCENARIO}-${Date.now()}.json`;
  return { [out]: JSON.stringify(data, null, 2), stdout: textSummary(data) };
}

function textSummary(data) {
  const m = data.metrics;
  const f = (x, d = 2) => (x === undefined ? "n/a" : Number(x).toFixed(d));
  const dur = m.http_req_duration ? m.http_req_duration.values : {};
  const lines = [
    "",
    `scenario=${SCENARIO} vus=${VUS} max_tokens=${MAX_TOKENS}`,
    `requests: ${m.http_reqs.values.count} (${f(m.http_reqs.values.rate, 3)} req/s), failed: ${f(m.http_req_failed.values.rate * 100)}%`,
    `latency ms: med=${f(dur.med, 0)} p90=${f(dur["p(90)"], 0)} p95=${f(dur["p(95)"], 0)} p99=${f(dur["p(99)"], 0)} max=${f(dur.max, 0)}`,
    `completion tokens: ${m.llm_completion_tokens ? m.llm_completion_tokens.values.count : 0}, per-request tok/s med=${m.llm_tokens_per_second ? f(m.llm_tokens_per_second.values.med, 1) : "n/a"}`,
    "",
  ];
  return lines.join("\n");
}
