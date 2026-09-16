# Runbooks

One page per alert, linked from the alert's `runbook` annotation. Every
runbook follows the same shape: **Symptoms → Check → Mitigate → Escalate →
Follow-up**. Commands assume the kind cluster; on EKS replace the context.

| Alert | Severity | Runbook |
|-------|----------|---------|
| AiplatformErrorBudgetBurnFast / Slow | page / ticket | [error-budget-burn.md](error-budget-burn.md) |
| AiplatformLatencySLOViolation | ticket | [latency.md](latency.md) |
| AiplatformWorkloadDown, AiplatformScrapeMissing | page / ticket | [workload-down.md](workload-down.md) |
| AiplatformQueueSaturated | ticket | [queue-saturated.md](queue-saturated.md) |
| AiplatformHPAMetricUnavailable | ticket | [hpa-metric-unavailable.md](hpa-metric-unavailable.md) |

## Incident template

```
Title:        <what users saw>
Severity:     page | ticket
Started:      <UTC>   Detected: <UTC, by alert or human>   Resolved: <UTC>
Impact:       <requests failed / latency / affected environments>
Timeline:     <UTC — action / observation>
Root cause:   <one paragraph>
Mitigation:   <what stopped the bleeding>
Follow-ups:   <issue links: fix, test, alert tuning, runbook edits>
```

Post-incident: add the timeline to `docs/benchmarks/` if it produced a
measurement, and update the runbook that should have caught it faster.
