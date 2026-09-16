import pytest

from aiplatform.errors import StepError
from aiplatform.steps.pipeline import Pipeline, Step, StepStatus


class Recorder:
    """Minimal reporter capturing events instead of printing."""

    def __init__(self):
        self.events = []

    def step_started(self, name):
        self.events.append(("start", name))

    def step_finished(self, name, status, detail, seconds):
        self.events.append((status, name, detail))


class Ok(Step):
    name = "ok step"

    def run(self, ctx):
        ctx["ran"] = ctx.get("ran", 0) + 1
        return "fine"


class Boom(Step):
    name = "boom"

    def run(self, ctx):
        raise StepError("it broke")


class Crash(Step):
    name = "crash"

    def run(self, ctx):
        raise RuntimeError("unexpected")


def test_runs_steps_in_order_and_reports():
    rep = Recorder()
    ctx = {}
    result = Pipeline(reporter=rep).run([Ok(), Ok()], ctx)
    assert result.succeeded
    assert ctx["ran"] == 2
    assert [e[0] for e in rep.events] == ["start", StepStatus.OK, "start", StepStatus.OK]
    assert rep.events[1][2] == "fine"


def test_stops_at_first_failure():
    rep = Recorder()
    ctx = {}
    result = Pipeline(reporter=rep).run([Ok(), Boom(), Ok()], ctx)
    assert not result.succeeded
    assert result.failed_step == "boom"
    assert "it broke" in result.error
    assert ctx["ran"] == 1
    assert rep.events[-1][0] == StepStatus.FAILED


def test_unexpected_exception_is_wrapped_not_raised():
    result = Pipeline(reporter=Recorder()).run([Crash()], {})
    assert not result.succeeded
    assert "unexpected" in result.error


def test_step_must_have_name():
    class Nameless(Step):
        def run(self, ctx):
            return None

    with pytest.raises(TypeError):
        Nameless()
