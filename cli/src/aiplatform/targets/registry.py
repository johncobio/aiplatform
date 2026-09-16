from aiplatform.errors import TargetError
from aiplatform.targets.base import Target
from aiplatform.targets.gitops import GitOpsTarget
from aiplatform.targets.kind import KindTarget
from aiplatform.targets.local import LocalDockerTarget

TARGETS: dict[str, type[Target]] = {
    LocalDockerTarget.name: LocalDockerTarget,
    KindTarget.name: KindTarget,
    GitOpsTarget.name: GitOpsTarget,
}


def get_target(name: str) -> Target:
    try:
        return TARGETS[name]()
    except KeyError:
        raise TargetError(f"unknown target {name!r}; available: {', '.join(TARGETS)}") from None
