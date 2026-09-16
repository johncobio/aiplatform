import json

import pytest

from aiplatform.addons import ORIGINAL_ANNOTATION, ScaleAddon
from aiplatform.errors import StepError
from aiplatform.steps.pipeline import Pipeline

LIST_KEY = "kubectl --context kind-aiplatform -n argocd get deployments,statefulsets"


def workloads(*specs):
    items = []
    for kind, name, replicas, annotations in specs:
        items.append(
            {
                "kind": kind,
                "metadata": {"name": name, "annotations": annotations},
                "spec": {"replicas": replicas},
            }
        )
    return json.dumps({"items": items})


def test_pause_annotates_and_scales_to_zero(runner):
    runner.responses[LIST_KEY] = workloads(
        ("Deployment", "server", 1, {}),
        ("StatefulSet", "controller", 1, {}),
        ("Deployment", "idle", 0, {}),
    )
    result = Pipeline().run([ScaleAddon(runner, "argocd", resume=False)], {})
    assert result.succeeded, result.error
    scales = [c for c in runner.calls if "scale" in c]
    assert [c[-1] for c in scales] == ["--replicas=0", "--replicas=0"]
    annotate = [c for c in runner.calls if "annotate" in c][0]
    assert f"{ORIGINAL_ANNOTATION}=1" in annotate


def test_resume_restores_original_counts(runner):
    runner.responses[LIST_KEY] = workloads(
        ("Deployment", "server", 0, {ORIGINAL_ANNOTATION: "2"}), ("Deployment", "fresh", 1, {})
    )
    result = Pipeline().run([ScaleAddon(runner, "argocd", resume=True)], {})
    assert result.succeeded, result.error
    scales = [c for c in runner.calls if "scale" in c]
    assert len(scales) == 1 and scales[0][-1] == "--replicas=2" and "server" in scales[0]


def test_unknown_addon_rejected(runner):
    with pytest.raises(StepError, match="unknown add-on"):
        ScaleAddon(runner, "nope", resume=False)


def test_empty_namespace_is_an_error(runner):
    runner.responses[LIST_KEY] = json.dumps({"items": []})
    result = Pipeline().run([ScaleAddon(runner, "argocd", resume=False)], {})
    assert not result.succeeded and "installed" in result.error
