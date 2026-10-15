# Demo walkthrough (7 minutes)

Use this as a spoken outline, not a script to paste all at once. Rehearse
before recording. Record your screen and narration yourself using macOS screen
recording, Zoom, or another recorder. Turn off notifications.

## Preparation (off camera)

1. Run `make check`. Keep its successful output available.
2. Select **one** inference endpoint. Prefer the EC2 endpoint once verified.
   Otherwise use the local qwen-server already deployed to kind, if healthy.
3. Verify `/health` for upstream llama.cpp, or `/readyz` for the built-in
   service. Do not run `make cluster-up` just before presenting: it starts all
   add-ons and can exhaust this laptop. Do not compile the model image on camera.
4. If using AWS, restrict inbound access to your IP and keep the lab session
   alive. Never display the credentials pane or terminal history containing keys.
5. Keep an actual saved health/chat response and the test log as backup evidence.

## 0:00–0:45 — Overview and repository

“This is a self-service platform for deploying and operating open-source model
inference. The developer declares the model and resources in YAML. The
platform handles validation and deployment, and exposes operational metrics.”

Show README and `services/qwen-server/aiplatform.yaml`. Explain CPU, memory,
the serving engine, and autoscaling. State where today's endpoint actually runs.

## 0:45–1:45 — Validation and architecture

```bash
uv run --project cli aiplatform validate --dir services/qwen-server
uv run --project cli aiplatform models
```

Show the architecture slide. Explain the **current prototype**, proposed
midpoint EC2 footprint, and later EKS design separately. Only call AWS components
deployed after checking the console and a successful request from the instance.

## 1:45–3:15 — Actual model inference

Set `DEMO_ENDPOINT` to the URL you have verified (no trailing slash). In another
terminal, run the following. The supplied public IP is a documentation example,
not a live service.

```bash
export DEMO_ENDPOINT=http://YOUR_VERIFIED_HOST:8000
curl --fail-with-body --connect-timeout 5 --max-time 90 \
  "$DEMO_ENDPOINT/v1/models" | python3 -m json.tool
curl --fail-with-body --connect-timeout 5 --max-time 90 \
  "$DEMO_ENDPOINT/v1/chat/completions" \
  -H 'Content-Type: application/json' \
  -d '{"messages":[{"role":"user","content":"Explain GitOps in one sentence."}],"max_tokens":32,"temperature":0.2}' \
  | python3 -m json.tool
```

Point out the model name, generated text, token usage, and finish reason.
Say this workload serves the model itself. Model responses may be inaccurate;
the engineering demo demonstrates deployment and operation, not model quality.

## 3:15–4:00 — Operational evidence

```bash
curl --fail --max-time 10 "$DEMO_ENDPOINT/metrics" \
  | rg '^(llamacpp:|llm_)' | head -20
```

Show native token counters and processing/queue metrics. If Grafana is already
healthy, show the dashboard. Otherwise explain the September 16 dashboard
verification using the recorded evidence. Do not start the entire stack just
for the recording. A direct EC2 demo does not imply Prometheus runs on EC2.

## 4:00–5:00 — Automation and validation

Show the current GitHub Actions run and fresh `make check` output. Explain
image publication, Terraform validation, policy checks, and local GitOps.
Distinguish “configuration validates” from “infrastructure is deployed.”
If remote CI is red, explain the actual failure rather than presenting an
older green run as current.

## 5:00–6:00 — Guardrails and approval

```bash
uv run --project cli aiplatform propose 'Add a NAT gateway' \
  --from-file examples/proposals/rejected-nat-gateway.json --dry-run
```

The expected result is rejection, with no apply. This fixture proves a policy
path. It does not demonstrate a live model generating the proposal. Show the
existing proposal PR if useful, and say it used a file provider.

## 6:00–7:00 — Reflection and next steps

Show the historical benchmark comparison and discuss one limitation: shared
CPU capacity, memory constraints, or the ingress monitoring blind spot.
Explain the next cloud milestone and the teardown command. Close by stating
what remains before the final submission, including real cloud validation.

## After recording

- Watch the whole video and check audible narration, readable terminal text,
  absence of credentials, and a duration of 5–10 minutes.
- Share the video and test access from a signed-out browser.
- Submit the link, public repository URL, and correctly named PPTX.
- Destroy only the project's cloud resources using its Terraform state.
