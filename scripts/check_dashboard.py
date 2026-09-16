"""Run every PromQL expression in a Grafana dashboard against Prometheus.

Catches typos and label mismatches without opening a browser:
  python scripts/check_dashboard.py deploy/observability/dashboards/llm-inference.json \
      http://prometheus.127.0.0.1.nip.io environment=staging workload=llm-service
"""

import json
import re
import sys
import urllib.parse
import urllib.request


def main() -> int:
    path, prom, *assigns = sys.argv[1:]
    variables = {"__rate_interval": "1m", "node_hourly_cost": "0.0168"}
    variables.update(dict(a.split("=", 1) for a in assigns))
    dash = json.load(open(path))
    failures = 0
    for panel in dash["panels"]:
        for target in panel.get("targets", []):
            expr = target["expr"]
            for k, v in variables.items():
                expr = expr.replace(f"${k}", v).replace("${" + k + "}", v)
            if re.search(r"\$[A-Za-z_{]", expr):
                print(f"UNRESOLVED  {panel['title']}: {expr}")
                failures += 1
                continue
            url = f"{prom}/api/v1/query?" + urllib.parse.urlencode({"query": expr})
            with urllib.request.urlopen(url, timeout=15) as resp:  # noqa: S310
                body = json.load(resp)
            if body["status"] != "success":
                print(f"ERROR       {panel['title']}: {body.get('error')}")
                failures += 1
                continue
            n = len(body["data"]["result"])
            optional = "[engine-specific]" in (panel.get("description") or "")
            status = "ok" if n else ("empty-opt" if optional else "EMPTY")
            print(f"{status:<11} {panel['title']} [{target['legendFormat']}]: {n} series")
            failures += 0 if (n or optional) else 1
    print(f"\n{failures} problem(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
