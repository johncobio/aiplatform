"""Turn a k6 summary plus Prometheus server-side metrics into a Markdown table.

  python loadtest/report.py loadtest/results/steady-*.json --prom http://prometheus.127.0.0.1.nip.io \
      --start 2026-09-16T22:00:00Z --end 2026-09-16T22:02:00Z
"""

import argparse
import json
import urllib.parse
import urllib.request



def prom_range_max(prom: str, expr: str, start: str, end: str, step: str = "15s") -> float | None:
    q = urllib.parse.urlencode({"query": expr, "start": start, "end": end, "step": step})
    with urllib.request.urlopen(f"{prom}/api/v1/query_range?{q}", timeout=20) as r:  # noqa: S310
        data = json.load(r)["data"]["result"]
    values = [float(v[1]) for series in data for v in series["values"] if v[1] not in ("NaN", "+Inf")]
    return max(values) if values else None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("summary")
    ap.add_argument("--prom")
    ap.add_argument("--start")
    ap.add_argument("--end")
    ap.add_argument("--env", default="staging")
    ap.add_argument("--workload", default="llm-service")
    args = ap.parse_args()
    sel = f'{{environment="{args.env}",workload="{args.workload}"}}'
    ns = f"aiplatform-{args.env}"
    d = json.load(open(args.summary))
    m = d["metrics"]
    dur = m["http_req_duration"]["values"]
    rows = [
        ("Requests", f"{m['http_reqs']['values']['count']:.0f}"),
        ("Throughput", f"{m['http_reqs']['values']['rate']:.3f} req/s"),
        ("Failed", f"{m['http_req_failed']['values']['rate'] * 100:.2f} %"),
        ("Latency median / p95 / p99 / max", f"{dur['med'] / 1000:.2f} / {dur['p(95)'] / 1000:.2f} / {dur['p(99)'] / 1000:.2f} / {dur['max'] / 1000:.2f} s"),
    ]
    if "llm_tokens_per_second" in m:
        rows.append(("Per-request generation speed (median)", f"{m['llm_tokens_per_second']['values']['med']:.1f} tok/s"))
    if "llm_completion_tokens" in m:
        secs = d["state"]["testRunDurationMs"] / 1000
        rows.append(("Completion tokens total / per second", f"{m['llm_completion_tokens']['values']['count']:.0f} / {m['llm_completion_tokens']['values']['count'] / secs:.1f}"))
    if args.prom and args.start and args.end:
        server = {
            "Max pending requests (server)": f"sum(aiplatform:llm_pending_requests{sel})",
            "Max ready replicas": f'kube_deployment_status_replicas_ready{{namespace="{ns}",deployment="{args.workload}"}}',
            "Max ingress P95 (5m window)": f"max(aiplatform:http_request_duration_seconds:p95_5m{sel})",
            "Max pod CPU (cores)": f'sum(rate(container_cpu_usage_seconds_total{{namespace="{ns}",container="inference",pod=~"{args.workload}-.*"}}[1m]))',
        }
        for label, expr in server.items():
            v = prom_range_max(args.prom, expr, args.start, args.end)
            rows.append((label, "n/a" if v is None else f"{v:.2f}"))
    print("| Measurement | Value |\n|---|---|")
    for k, v in rows:
        print(f"| {k} | {v} |")


if __name__ == "__main__":
    main()
