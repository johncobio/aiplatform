import json

import pytest

from preview_demo.intent import decode_intent
from preview_demo.workflow import DemoError, Spec


def test_model_returns_only_the_bounded_spec():
    assert decode_intent('{"version":2,"minutes":15}') == Spec(2, 15)


@pytest.mark.parametrize(
    "value",
    [
        {"version": 1, "minutes": 15, "cidr": "0.0.0.0/0"},
        {"version": 2, "minutes": 10},
        {"version": 3, "minutes": 30},
        {"version": "2", "minutes": 15},
        {"version": True, "minutes": 15},
        {"version": None, "minutes": None},
    ],
)
def test_bad_model_outputs_never_become_a_spec(value):
    with pytest.raises(DemoError, match="could not interpret"):
        decode_intent(json.dumps(value))
