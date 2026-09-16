"""Chaos experiments against a running aiplatform workload, with measured recovery.

  python chaos/experiment.py pod-kill        --env dev --workload qwen-server
  python chaos/experiment.py adapter-outage  --env dev --workload qwen-server
  python chaos/experiment.py ingress-restart --env dev --workload qwen-server

Each experiment keeps a 1-VU k6 load running, injects one fault at
--inject-at seconds, measures time-to-recovery from the cluster's own
signals, and appends a Markdown row to chaos/results/<experiment>.md.
No chaos platform is used on purpose: every fault is a plain kubectl action
an on-call engineer could reproduce by hand.
"""

import argparse
import json
import subprocess
import sys
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

CTX = ["kubectl", "--context", "kind-aiplatform"]


def sh(*cmd, check=True, capture=True):
    return subprocess.run(cmd, check=check, capture_output=capture, text=True)


def kubectl(*args, check=True):
    return sh(*CTX, *args, check=check)


def http_ok(url, timeout=5):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:  # noqa: S310
            return r.status == 200
    except Exception:  # noqa: BLE001
        return False


def wait_until(pred, timeout, interval=1.0):
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout:
        if pred():
            return round(time.monotonic() - t0, 1)
        time.sleep(interval)
    return None


def start_load(url, duration, summary):
    return subprocess.Popen(
        ["k6", "run", "--quiet", "-e", f"BASE_URL={url}", "-e", "SCENARIO=steady", "-e", "VUS=1",
         "-e", f"DURATION={duration}s", "-e", f"SUMMARY={summary}", "loadtest/k6/chat.js"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


# --- experiments ------------------------------------------------------------

def pod_kill(ns, workload, url):
    """Delete the serving pod; recovery = a *new* pod is Ready and the endpoint answers."""
    sel = f"app.kubernetes.io/instance={workload}"

    def ready_new_pod():
        out = kubectl("-n", ns, "get", "pod", "-l", sel, "-o", "json", check=False).stdout
        for pod in json.loads(out or '{"items": []}')["items"]:
            if pod["metadata"].get("deletionTimestamp"):
                continue  # the old pod, still terminating
            conds = {c["type"]: c["status"] for c in pod["status"].get("conditions", [])}
            if conds.get("Ready") == "True":
                return True
        return False

    kubectl("-n", ns, "delete", "pod", "-l", sel, "--wait=false")
    ready = wait_until(ready_new_pod, 600)
    serving = wait_until(lambda: http_ok(f"{url}/v1/models"), 120)
    return {"pod ready (s)": ready, "endpoint serving (s)": serving}


def adapter_outage(ns, workload, url):
    """Scale prometheus-adapter to 0: the HPA loses its metric. Restore and measure."""
    def scaling_active():
        out = kubectl("-n", ns, "get", "hpa", workload, "-o",
                      'jsonpath={.status.conditions[?(@.type=="ScalingActive")].status}', check=False).stdout
        return out.strip()
    kubectl("-n", "observability", "scale", "deploy", "prometheus-adapter", "--replicas=0")
    degraded = wait_until(lambda: scaling_active() == "False", 300, interval=5)
    kubectl("-n", "observability", "scale", "deploy", "prometheus-adapter", "--replicas=1")
    restored = wait_until(lambda: scaling_active() == "True", 300, interval=5)
    return {"HPA lost metric after (s)": degraded, "HPA metric restored after (s)": restored,
            "endpoint serving (s)": 0.0 if http_ok(f"{url}/v1/models") else None}


def ingress_restart(ns, workload, url):
    """Restart the single ingress-nginx controller (Recreate strategy): a data-plane outage."""
    kubectl("-n", "ingress-nginx", "rollout", "restart", "deploy/ingress-nginx-controller")
    down = wait_until(lambda: not http_ok(f"{url}/v1/models", timeout=2), 60, interval=0.5)
    back = wait_until(lambda: http_ok(f"{url}/v1/models"), 300, interval=1)
    return {"ingress went down after (s)": down, "ingress serving again (s)": back}


EXPERIMENTS = {"pod-kill": pod_kill, "adapter-outage": adapter_outage, "ingress-restart": ingress_restart}


def prom_max(prom, expr, start, end):
    q = urllib.parse.urlencode({"query": expr, "start": start, "end": end, "step": "15s"})
    with urllib.request.urlopen(f"{prom}/api/v1/query_range?{q}", timeout=20) as r:  # noqa: S310
        data = json.load(r)["data"]["result"]
    vals = [float(v[1]) for s in data for v in s["values"] if v[1] not in ("NaN", "+Inf")]
    return max(vals) if vals else None


def main():
    import urllib.parse  # noqa: F401 - used in prom_max via urllib.parse
    ap = argparse.ArgumentParser()
    ap.add_argument("experiment", choices=EXPERIMENTS)
    ap.add_argument("--env", default="dev")
    ap.add_argument("--workload", default="qwen-server")
    ap.add_argument("--duration", type=int, default=150)
    ap.add_argument("--inject-at", type=int, default=30)
    ap.add_argument("--prom", default="http://prometheus.127.0.0.1.nip.io")
    args = ap.parse_args()

    ns = f"aiplatform-{args.env}"
    url = f"http://{args.workload}.{args.env}.127.0.0.1.nip.io"
    summary = Path("chaos/results") / f"{args.experiment}-{int(time.time())}.json"
    summary.parent.mkdir(parents=True, exist_ok=True)
    if not http_ok(f"{url}/v1/models"):
        sys.exit(f"{url} is not serving; deploy the workload first")

    start = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    load = start_load(url, args.duration, summary)
    time.sleep(args.inject_at)
    injected = datetime.now(UTC).strftime("%H:%M:%S")
    t0 = time.monotonic()
    measures = EXPERIMENTS[args.experiment](ns, args.workload, url)
    measures["experiment wall (s)"] = round(time.monotonic() - t0, 1)
    load.wait()
    end = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    k6 = json.load(open(summary))["metrics"]
    reqs = k6["http_reqs"]["values"]["count"]
    failed = k6["http_req_failed"]["values"]["rate"] * reqs
    p95 = k6["http_req_duration"]["values"]["p(95)"] / 1000
    sli = None
    try:
        sli = prom_max(args.prom, f'1 - aiplatform:sli_availability:ratio_rate5m{{environment="{args.env}",workload="{args.workload}"}}', start, end)
    except Exception:  # noqa: BLE001
        pass

    row = {
        "experiment": args.experiment, "injected at": injected, **measures,
        "requests during run": int(reqs), "failed requests": int(round(failed)),
        "client p95 (s)": round(p95, 2),
        "max 5xx ratio (5m SLI)": None if sli is None else round(sli, 4),
    }
    out = Path("chaos/results") / f"{args.experiment}.md"
    header = "| " + " | ".join(row) + " |\n|" + "---|" * len(row) + "\n"
    line = "| " + " | ".join("n/a" if v is None else str(v) for v in row.values()) + " |\n"
    if not out.exists():
        out.write_text(header)
    out.write_text(out.read_text() + line)
    print(header + line)


if __name__ == "__main__":
    import urllib.parse
    main()
