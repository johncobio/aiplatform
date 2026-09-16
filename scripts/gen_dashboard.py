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

rate = f"sum(rate(llm_requests_total{SEL}[$__rate_interval]))"
q = lambda p: f"histogram_quantile({p}, sum(rate(llm_request_duration_seconds_bucket{SEL}[$__rate_interval])) by (le))"
err = f'(sum(rate(llm_requests_total{{environment="$environment",workload="$workload",status="error"}}[5m])) or vector(0)) / clamp_min(sum(rate(llm_requests_total{SEL}[5m])), 1e-9)'
ready = f'kube_deployment_status_replicas_ready{{{NS},deployment="$workload"}}'
desired = f'kube_deployment_spec_replicas{{{NS},deployment="$workload"}}'
hpa = f'kube_horizontalpodautoscaler_status_desired_replicas{{{NS},horizontalpodautoscaler="$workload"}}'
tok = f"sum(rate(llm_completion_tokens_total{SEL}[$__rate_interval]))"
ptok = f"sum(rate(llm_prompt_tokens_total{SEL}[$__rate_interval]))"
tps50 = f"histogram_quantile(0.5, sum(rate(llm_generation_tokens_per_second_bucket{SEL}[$__rate_interval])) by (le))"
cpu = f"sum(rate(container_cpu_usage_seconds_total{{{NS},{POD}}}[$__rate_interval]))"
cpu_lim = f'sum(kube_pod_container_resource_limits{{{NS},{POD},resource="cpu"}})'
mem = f"sum(container_memory_working_set_bytes{{{NS},{POD}}})"
mem_lim = f'sum(kube_pod_container_resource_limits{{{NS},{POD},resource="memory"}})'
cost_hour = f"$node_hourly_cost * sum({ready})"
cost_1k = f"($node_hourly_cost * sum({ready})) / clamp_min(sum(rate(llm_requests_total{SEL}[1h])) * 3600, 1e-9) * 1000"

panels = [
    row("Headline", 0),
    stat("Request rate", rate, "reqps", 0, 1),
    stat("P95 latency", q(0.95), "s", 4, 1),
    stat("Tokens / s", tok, "short", 8, 1, decimals=1),
    stat("Error rate", err, "percentunit", 12, 1, thresholds=[{"color": GREEN, "value": None}, {"color": ORANGE, "value": 0.01}, {"color": RED, "value": 0.05}]),
    stat("Ready replicas", f"sum({ready})", "short", 16, 1, decimals=0),
    stat("Queue depth", f"sum(llm_queue_depth{SEL})", "short", 20, 1, decimals=0,
         thresholds=[{"color": GREEN, "value": None}, {"color": ORANGE, "value": 1}, {"color": RED, "value": 3}],
         desc="Requests waiting for a generation slot. The V5 autoscaling signal."),
    row("Traffic and latency", 5),
    ts("Requests / s by status", [(f"sum(rate(llm_requests_total{SEL}[$__rate_interval])) by (status)", "{{status}}")],
       "reqps", 0, 6, colors={"ok": GREEN, "error": RED, "rejected": ORANGE}, stack=True),
    ts("Latency P50 / P95 / P99", [(q(0.5), "p50"), (q(0.95), "p95"), (q(0.99), "p99")],
       "s", 12, 6, colors={"p50": BLUE_L, "p95": BLUE_M, "p99": BLUE_D}, fill=0,
       desc="End-to-end request time including queue wait (llm_request_duration_seconds)."),
    row("Inference", 14),
    ts("Tokens / s", [(tok, "completion tokens/s"), (ptok, "prompt tokens/s")], "short", 0, 15,
       colors={"completion tokens/s": BLUE_M, "prompt tokens/s": GRAY}, fill=0),
    ts("Per-request generation speed (P50)", [(tps50, "tok/s per request")], "short", 12, 15, w=6,
       colors={"tok/s per request": PURPLE}, fill=0, desc="Median of llm_generation_tokens_per_second."),
    ts("Queue depth and in-flight", [(f"sum(llm_queue_depth{SEL})", "queued"), (f"sum(llm_inflight_requests{SEL})", "in-flight")],
       "short", 18, 15, w=6, colors={"queued": ORANGE, "in-flight": BLUE_M}),
    row("Capacity", 23),
    ts("Replicas", [(f"sum({ready})", "ready"), (f"sum({desired})", "desired"), (f"sum({hpa})", "hpa target")],
       "short", 0, 24, w=8, colors={"ready": GREEN, "desired": GRAY, "hpa target": PURPLE}, fill=0),
    ts("CPU (cores)", [(cpu, "used"), (cpu_lim, "limit")], "short", 8, 24, w=8,
       colors={"used": BLUE_M, "limit": GRAY}, fill=0),
    ts("Memory (working set)", [(mem, "used"), (mem_lim, "limit")], "bytes", 16, 24, w=8,
       colors={"used": BLUE_M, "limit": GRAY}, fill=0),
    row("Model and cost (estimates)", 32),
    stat("Model load time", f"max(llm_model_load_seconds{SEL})", "s", 0, 33, w=6, decimals=1),
    stat("Est. infra cost / hour", cost_hour, "currencyUSD", 6, 33, w=6, decimals=4,
         desc="node_hourly_cost × ready replicas. An estimate: one replica is assumed to occupy one node's worth of the configured hourly price."),
    stat("Est. cost per 1k requests", cost_1k, "currencyUSD", 12, 33, w=6, decimals=4,
         desc="Estimated hourly cost divided by requests per hour (1h window), ×1000."),
    stat("Model", f"llm_model_info{SEL}", "none", 18, 33, w=6, decimals=0),
]
# the model info stat should show the label, not the value
panels[-1]["options"]["textMode"] = "name"
panels[-1]["options"]["reduceOptions"]["fields"] = "/^model$/"
panels[-1]["targets"][0]["format"] = "table"
panels[-1]["targets"][0]["instant"] = True

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
         "query": {"query": "label_values(llm_requests_total, environment)", "refId": "env"},
         "definition": "label_values(llm_requests_total, environment)", "refresh": 2, "sort": 1,
         "current": {"selected": False, "text": "staging", "value": "staging"}},
        {"name": "workload", "type": "query", "datasource": DS, "label": "Workload",
         "query": {"query": 'label_values(llm_requests_total{environment="$environment"}, workload)', "refId": "wl"},
         "definition": 'label_values(llm_requests_total{environment="$environment"}, workload)', "refresh": 2, "sort": 1,
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
