# 0011 — SLOs measured at the ingress, burn-rate alerts, chaos with plain kubectl

2026-09-16 · Accepted

## Context

V8 needs SLOs, alerts, chaos testing and runbooks on a platform that serves
several inference engines with different native metrics, on a laptop that
cannot afford another operator.

## Decision

- **SLIs come from ingress-nginx**, not from the engines: availability is
  the non-5xx ratio and latency the share of requests under 5 s, per
  `(environment, workload)`. This holds every engine to the same standard
  and survives engine swaps (ADR 0009). Targets: 99.5 % / 30 d and 90 % < 5 s / 1 h,
  chosen from the V5 measurements and stated with their reasoning in
  `docs/RELIABILITY.md`.
- **Multi-window multi-burn-rate alerts** (14.4× over 1 h+5 m pages, 6× over
  6 h+30 m tickets) plus symptom alerts for the failure modes actually
  observed while building the platform. Every alert links a runbook.
- **Alertmanager is enabled** in the existing kube-prometheus-stack with a
  null receiver locally and a documented Slack/webhook example that reads
  its URL from a Secret.
- **Chaos with kubectl.** `chaos/experiment.py` injects pod deletion,
  metrics-pipeline loss and an ingress data-plane restart while a k6 load
  runs, and measures recovery from cluster signals. No Litmus/Chaos Mesh:
  the faults an on-call engineer can reproduce by hand are the ones worth
  measuring first, and the laptop has no memory for another controller.

## Consequences

- The reliability story is consistent end to end: contract metrics →
  SLIs → burn-rate alerts → runbooks → experiments that exercise them.
- Ingress-based SLIs miss failures before the ingress (DNS, the controller
  itself); the ingress-restart experiment quantifies that blind spot.
- Latency SLO at 5 s is a CPU-era number and must be retargeted for GPU
  engines on EKS.
