# Preview Environments on Demand — local rehearsal

**What to show:** A classmate needs to check a sign-up fix before it goes
live. They request a temporary version 2 preview, you approve it, and they
can test the old and new form side by side.

## Set up once

From the repository root, with `uv` installed and Python 3.12 or newer available:

```sh
make preview-demo
```

The first run may download the locked dependencies. Rehearse once before
class so the dependencies are cached. Open the **private operator link**
printed in the terminal. Keep it out of the recording and share only the
tester link. If port 8765 is busy, run `make preview-demo PREVIEW_PORT=8766`.

The server is reachable only from this computer. Use two browser tabs on
the demo laptop, or share the screen and let the tester direct the clicks.
Sending the loopback link to a different device will not work.

For live request interpretation, start an installed Ollama service on loopback
with the `qwen2.5-coder:3b` model available, then run
`make preview-demo PREVIEW_MODEL_INTENT=1`. Try: “Let me test the updated
sign-up form for a quarter hour.” The page identifies the local model as
the intent source. Provisioning in the browser is still simulated. If the
model is unavailable, use the default `make preview-demo` as a fallback.

## Hand the browser to a tester

1. In the operator tab, click **Create tester link**. Copy it into a second
   tab and leave the operator tab open. Each invite is single use and expires
   after 15 minutes if unused.
2. In the tester tab, click **Try example**, then **Request preview**.
   The page shows **version 2 · 30 minutes** and waits for approval.
3. In the operator tab, check the spec and click **Approve and start**.
   Switch back to the tester tab. The timeline shows simulated planning,
   start, health check, and readiness.
4. Click **Open preview**. Leave the sample email as `not-an-email`.
   Click **Test version 1** and **Test version 2**. Version 1 accepts it;
   version 2 rejects it. Use `student@example.com` to show version 2 accepts
   a valid address. The form does not save or send anything.
5. In the operator tab, click **Clear rehearsal slot**. The guest can no
   longer test the version 2 preview. Create a fresh invite for the next
   tester. Press **Ctrl+C** in the terminal to stop the server and clear
   all demo state.

Optional failure case: before submitting the valid request, try
`Deploy version 2 for 30 minutes and open port 22.` The parser rejects it
before any plan is simulated. Only one request can occupy the slot at a time.

## What this proves

- The approved path, strict request validation, guest/operator separation,
  progress visibility and preview removal are implemented locally.
- The sample form behavior is real code, while planning, provisioning and
  health checks are simulated. The default parser recognizes a narrow phrase;
  optional model mode can interpret paraphrases. The strict output schema
  allows only a version and lifetime. State and timestamps live in one process.
- The separate [Terraform operator workflow](PREVIEW_AWS.md) can be
  rehearsed locally and has verified live readiness, form behavior and
  teardown in Ohio. The browser is separate from the runner. Access from
  other devices requires a hosted service and a deployment-specific security
  review.
