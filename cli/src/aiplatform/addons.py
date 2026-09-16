"""Pause and resume platform add-ons by scaling their workloads to zero.

On a memory-constrained laptop, Argo CD and the observability stack do not
fit next to an LLM workload at the same time. Pausing keeps the Helm
releases, CRDs, and desired state intact; only the pods go away.
"""

import json

from aiplatform import shell
from aiplatform.errors import StepError
from aiplatform.steps.pipeline import Context, Step
from aiplatform.targets.kind import KUBE_CONTEXT

# addon name -> (namespace, workload-name filter or None for everything in it).
# Finer-grained entries let a laptop keep Prometheus + the adapter (needed by
# the HPA) while shedding the UI and tracing pods.
ADDONS: dict[str, tuple[str, list[str] | None]] = {
    "argocd": ("argocd", None),
    "observability": ("observability", None),
    "metrics": (
        "observability",
        [
            "prometheus-prom-prometheus",
            "prom-operator",
            "kube-prometheus-stack-kube-state-metrics",
            "prometheus-adapter",
        ],
    ),
    "grafana": ("observability", ["kube-prometheus-stack-grafana"]),
    "tracing": ("observability", ["jaeger", "opentelemetry-collector"]),
}

# Operators/controllers restore replica counts themselves, so resume scales
# everything that has a recorded original count back to it.
ORIGINAL_ANNOTATION = "aiplatform.io/original-replicas"


def _kubectl(namespace: str, *args: str) -> list[str]:
    return ["kubectl", "--context", KUBE_CONTEXT, "-n", namespace, *args]


class ScaleAddon(Step):
    def __init__(self, run: shell.Runner, addon: str, resume: bool) -> None:
        if addon not in ADDONS:
            raise StepError(f"unknown add-on {addon!r}; choose from {', '.join(ADDONS)}")
        self.name = f"{addon} {'resumed' if resume else 'paused'}"
        super().__init__()
        self._run = run
        self.addon, self.resume = addon, resume
        self.namespace, self.only = ADDONS[addon]

    def run(self, ctx: Context) -> str | None:
        proc = self._run(
            _kubectl(self.namespace, "get", "deployments,statefulsets", "-o", "json"), check=False
        )
        if proc.returncode != 0:
            raise StepError(
                f"cannot list workloads in {self.namespace}: {proc.stderr.strip()[-200:]}"
            )
        items = json.loads(proc.stdout or '{"items": []}').get("items", [])
        if not items:
            raise StepError(f"no workloads found in namespace {self.namespace!r}; is it installed?")
        changed = 0
        for item in items:
            kind = item["kind"].lower()
            name = item["metadata"]["name"]
            if self.only is not None and name not in self.only:
                continue
            current = int(item["spec"].get("replicas") or 0)
            annotations = item["metadata"].get("annotations") or {}
            if self.resume:
                target = int(annotations.get(ORIGINAL_ANNOTATION, 1))
                if current == target:
                    continue
            else:
                target = 0
                if current == 0:
                    continue
                self._run(
                    _kubectl(
                        self.namespace,
                        "annotate",
                        kind,
                        name,
                        f"{ORIGINAL_ANNOTATION}={current}",
                        "--overwrite",
                    )  # fmt: skip
                )
            self._run(_kubectl(self.namespace, "scale", kind, name, f"--replicas={target}"))
            changed += 1
        return f"{changed} workload(s) scaled in {self.namespace}"
