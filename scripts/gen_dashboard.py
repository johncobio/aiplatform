"""Generate deploy/observability/dashboards/llm-inference.json (Grafana 11 schema)."""
import json, sys

SEL = '{environment="$environment",workload="$workload"}'
NS = 'namespace="aiplatform-$environment"'
POD = 'pod=~"$workload-.*",container="inference"'
DS = {"type": "prometheus", "uid": "${datasource}"}

# Fixed hues (never cycled): sequential blues for latency quantiles, semantic red for errors.
BLUE_L, BLUE_M, BLUE_D = "#8AB4F8", "#4285F4", "#174EA6"
GREEN, RED, ORANGE, PURPLE, GRAY = "#34A853", "#EA4335", "#F29900", "#A142F4", "#9AA0A6"

_id = iter(range(1, 200))

def target(expr, legend, ref="A"):
    return {"datasource": DS, "expr": expr, "legendFormat": legend, "refId": ref, "range": True}

def stat(title, expr, unit, x, y, w=4, h=4, decimals=2, thresholds=None, desc=""):
    fc = {"unit": unit, "decimals": decimals, "color": {"mode": "fixed", "fixedColor": BLUE_M}}
    if thresholds:
        fc["color"] = {"mode": "thresholds"}
        fc["thresholds"] = {"mode": "absolute", "steps": thresholds}
    return {
        "id": next(_id), "type": "stat", "title": title, "description": desc, "datasource": DS,
        "gridPos": {"x": x, "y": y, "w": w, "h": h},
        "targets": [target(expr, title)],
        "fieldConfig": {"defaults": fc, "overrides": []},
        "options": {"reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
                    "colorMode": "value", "graphMode": "area", "textMode": "value", "justifyMode": "center"},
    }

def ts(title, targets, unit, x, y, w=12, h=8, colors=None, desc="", stack=False, fill=10, min0=True):
    overrides = []
    for legend, color in (colors or {}).items():
        overrides.append({"matcher": {"id": "byName", "options": legend},
                          "properties": [{"id": "color", "value": {"mode": "fixed", "fixedColor": color}}]})
    defaults = {"unit": unit, "color": {"mode": "palette-classic"},
                "custom": {"lineWidth": 2, "fillOpacity": fill, "pointSize": 4, "showPoints": "never",
                           "spanNulls": True, "stacking": {"mode": "normal" if stack else "none"}}}
    if min0:
        defaults["min"] = 0
    return {
        "id": next(_id), "type": "timeseries", "title": title, "description": desc, "datasource": DS,
        "gridPos": {"x": x, "y": y, "w": w, "h": h},
        "targets": [target(e, l, chr(65 + i)) for i, (e, l) in enumerate(targets)],
        "fieldConfig": {"defaults": defaults, "overrides": overrides},
        "options": {"legend": {"displayMode": "list", "placement": "bottom", "showLegend": True},
                    "tooltip": {"mode": "multi", "sort": "desc"}},
    }

def row(title, y):
    return {"id": next(_id), "type": "row", "title": title, "collapsed": False,
            "gridPos": {"x": 0, "y": y, "w": 24, "h": 1}, "panels": []}

rate = f"sum(aiplatform:http_requests:rate5m{SEL})"
q = lambda p: f"max(aiplatform:http_request_duration_seconds:p{p}_5m{SEL})"
qn = lambda p: f"max(aiplatform:llm_request_duration_seconds:p{p}_5m{SEL})"
err = f'(sum(aiplatform:http_requests:rate5m{{environment="$environment",workload="$workload",status=~"5.."}}) or vector(0)) / clamp_min(sum(aiplatform:http_requests:rate5m{SEL}), 1e-9)'
ready = f'kube_deployment_status_replicas_ready{{{NS},deployment="$workload"}}'
desired = f'kube_deployment_spec_replicas{{{NS},deployment="$workload"}}'
hpa = f'kube_horizontalpodautoscaler_status_desired_replicas{{{NS},horizontalpodautoscaler="$workload"}}'
tok = f"sum(aiplatform:llm_completion_tokens:rate5m{SEL})"
ptok = f"sum(aiplatform:llm_prompt_tokens:rate5m{SEL})"
tps50 = f"max(aiplatform:llm_generation_tokens_per_second:p50_5m{SEL})"
cpu = f"sum(rate(container_cpu_usage_seconds_total{{{NS},{POD}}}[$__rate_interval]))"
cpu_lim = f'sum(kube_pod_container_resource_limits{{{NS},{POD},resource="cpu"}})'
mem = f"sum(container_memory_working_set_bytes{{{NS},{POD}}})"
mem_lim = f'sum(kube_pod_container_resource_limits{{{NS},{POD},resource="memory"}})'
cost_hour = f"$node_hourly_cost * sum({ready})"
cost_1k = f"($node_hourly_cost * sum({ready})) / clamp_min(sum(aiplatform:http_requests:rate5m{SEL}) * 3600, 1e-9) * 1000"

panels = [
    row("Headline", 0),
    stat("Request rate", rate, "reqps", 0, 1),
    stat("P95 latency (ingress)", q(95), "s", 4, 1),
    stat("Tokens / s", tok, "short", 8, 1, decimals=1),
    stat("Error rate", err, "percentunit", 12, 1, thresholds=[{"color": GREEN, "value": None}, {"color": ORANGE, "value": 0.01}, {"color": RED, "value": 0.05}]),
    stat("Ready replicas", f"sum({ready})", "short", 16, 1, decimals=0),
    stat("Pending requests", f"sum(aiplatform:llm_pending_requests{SEL})", "short", 20, 1, decimals=0,
         thresholds=[{"color": GREEN, "value": None}, {"color": ORANGE, "value": 1}, {"color": RED, "value": 3}],
         desc="Requests queued or generating across replicas (aiplatform:llm_pending_requests). The autoscaling signal."),
    row("SLOs (docs/RELIABILITY.md)", 5),
    stat("Availability (5m)", f"min(aiplatform:sli_availability:ratio_rate5m{SEL})", "percentunit", 0, 6, w=6, decimals=3,
         thresholds=[{"color": RED, "value": None}, {"color": ORANGE, "value": 0.99}, {"color": GREEN, "value": 0.995}],
         desc="Non-5xx share at the ingress. SLO 99.5% / 30d."),
    stat("Requests < 5 s (1h)", f"min(aiplatform:sli_latency_fast:ratio_rate1h{SEL})", "percentunit", 6, 6, w=6, decimals=3,
         thresholds=[{"color": RED, "value": None}, {"color": ORANGE, "value": 0.85}, {"color": GREEN, "value": 0.90}],
         desc="Latency SLI. SLO 90% within 5 s / 1h."),
    stat("Error budget remaining (30d)", f"min(aiplatform:error_budget_remaining:ratio{SEL})", "percentunit", 12, 6, w=6, decimals=2,
         thresholds=[{"color": RED, "value": None}, {"color": ORANGE, "value": 0.1}, {"color": GREEN, "value": 0.5}],
         desc="1 − consumed/budget. Policy thresholds at 50% and 10%."),
    stat("Burn rate (1h)", f"max((1 - aiplatform:sli_availability:ratio_rate1h{SEL}) / 0.005)", "short", 18, 6, w=6, decimals=2,
         thresholds=[{"color": GREEN, "value": None}, {"color": ORANGE, "value": 6}, {"color": RED, "value": 14.4}],
         desc="Error rate ÷ budget rate. Page at 14.4, ticket at 6."),
    row("Traffic and latency", 10),
    ts("Requests / s at ingress by HTTP status", [(f"sum(aiplatform:http_requests:rate5m{SEL}) by (status)", "{{status}}")],
       "reqps", 0, 11, colors={"200": GREEN, "500": RED, "503": ORANGE, "429": ORANGE}, stack=True,
       desc="Measured by ingress-nginx: identical for every engine."),
    ts("Latency at ingress P50 / P95 / P99", [(q(50), "p50"), (q(95), "p95"), (q(99), "p99")],
       "s", 12, 11, colors={"p50": BLUE_L, "p95": BLUE_M, "p99": BLUE_D}, fill=0,
       desc="nginx_ingress_controller_request_duration_seconds for this workload's Ingress; engine-agnostic."),
    ts("Engine-reported latency P50 / P95 / P99", [(qn(50), "p50"), (qn(95), "p95"), (qn(99), "p99")],
       "s", 0, 19, colors={"p50": BLUE_L, "p95": BLUE_M, "p99": BLUE_D}, fill=0,
       desc="From the engine's own histogram (builtin llm_request_duration_seconds, vLLM e2e latency). Empty for llama.cpp server, which has none."),
    ts("Requests / s reported by engine, by status", [(f"sum(aiplatform:llm_requests:rate5m{SEL}) by (status)", "{{status}}")],
       "reqps", 12, 19, colors={"ok": GREEN, "error": RED, "rejected": ORANGE}, stack=True,
       desc="Engine-native request accounting where available."),
    row("Inference", 27),
    ts("Tokens / s", [(tok, "completion tokens/s"), (ptok, "prompt tokens/s")], "short", 0, 28,
       colors={"completion tokens/s": BLUE_M, "prompt tokens/s": GRAY}, fill=0),
    ts("Per-request generation speed (P50)", [(tps50, "tok/s per request")], "short", 12, 28, w=6,
       colors={"tok/s per request": PURPLE}, fill=0, desc="Median of llm_generation_tokens_per_second."),
    ts("Pending requests (queued + in-flight)", [(f"sum(aiplatform:llm_pending_requests{SEL})", "pending"), (f"sum(aiplatform:llm_pending_requests{SEL}) / clamp_min(sum({ready}), 1)", "per pod (HPA signal)")],
       "short", 18, 28, w=6, colors={"pending": ORANGE, "per pod (HPA signal)": BLUE_M}, fill=0),
    row("Capacity", 36),
    ts("Replicas", [(f"sum({ready})", "ready"), (f"sum({desired})", "desired"), (f"sum({hpa})", "hpa target")],
       "short", 0, 37, w=8, colors={"ready": GREEN, "desired": GRAY, "hpa target": PURPLE}, fill=0),
    ts("CPU (cores)", [(cpu, "used"), (cpu_lim, "limit")], "short", 8, 37, w=8,
       colors={"used": BLUE_M, "limit": GRAY}, fill=0),
    ts("Memory (working set)", [(mem, "used"), (mem_lim, "limit")], "bytes", 16, 37, w=8,
       colors={"used": BLUE_M, "limit": GRAY}, fill=0),
    row("Model and cost (estimates)", 45),
    stat("Model load time (builtin)", f"max(llm_model_load_seconds{SEL})", "s", 0, 46, w=4, decimals=1),
    stat("Est. infra cost / hour", cost_hour, "currencyUSD", 4, 46, w=5, decimals=4,
         desc="node_hourly_cost × ready replicas. An estimate: one replica is assumed to occupy one node's worth of the configured hourly price."),
    stat("Est. cost per 1k requests", cost_1k, "currencyUSD", 9, 46, w=5, decimals=4,
         desc="Estimated hourly cost divided by requests per hour (1h window), ×1000."),
    stat("Model", f"count by (model) (up{SEL})", "none", 14, 46, w=5, decimals=0),
    stat("Engine", f"count by (engine) (up{SEL})", "none", 19, 46, w=5, decimals=0),
]
# Panels fed only by engines that expose the metric: the checker treats EMPTY as expected.
for pnl in panels:
    if pnl["title"] in ("Engine-reported latency P50 / P95 / P99", "Requests / s reported by engine, by status",
                        "Model load time (builtin)"):
        pnl["description"] = (pnl.get("description") or "") + " [engine-specific]"

# the model/engine stats show the label, not the value
for pnl in panels[-2:]:
    pnl["options"]["textMode"] = "name"
    pnl["targets"][0]["instant"] = True
panels[-2]["options"]["reduceOptions"]["fields"] = ""
panels[-2]["targets"][0]["legendFormat"] = "{{model}}"
panels[-1]["targets"][0]["legendFormat"] = "{{engine}}"

dashboard = {
    "uid": "aiplatform-llm-inference",
    "title": "LLM Inference",
    "tags": ["aiplatform", "llm"],
    "timezone": "browser",
    "schemaVersion": 39,
    "version": 1,
    "editable": True,
    "graphTooltip": 1,
    "refresh": "15s",
    "time": {"from": "now-30m", "to": "now"},
    "templating": {"list": [
        {"name": "datasource", "type": "datasource", "query": "prometheus", "label": "Data source",
         "current": {"selected": False, "text": "Prometheus", "value": "Prometheus"}, "hide": 0},
        {"name": "environment", "type": "query", "datasource": DS, "label": "Environment",
         "query": {"query": "label_values(aiplatform:llm_pending_requests, environment)", "refId": "env"},
         "definition": "label_values(aiplatform:llm_pending_requests, environment)", "refresh": 2, "sort": 1,
         "current": {"selected": False, "text": "staging", "value": "staging"}},
        {"name": "workload", "type": "query", "datasource": DS, "label": "Workload",
         "query": {"query": 'label_values(aiplatform:llm_pending_requests{environment="$environment"}, workload)', "refId": "wl"},
         "definition": 'label_values(aiplatform:llm_pending_requests{environment="$environment"}, workload)', "refresh": 2, "sort": 1,
         "current": {"selected": False, "text": "llm-service", "value": "llm-service"}},
        {"name": "node_hourly_cost", "type": "textbox", "label": "Node $/hour (estimate)",
         "query": "0.0168", "current": {"selected": False, "text": "0.0168", "value": "0.0168"},
         "description": "Hourly on-demand price of the node type a replica occupies. Default: t4g.small us-east-1."},
    ]},
    "panels": panels,
}
out = sys.argv[1]
with open(out, "w") as f:
    json.dump(dashboard, f, indent=2)
print(out, len(panels), "panels")
