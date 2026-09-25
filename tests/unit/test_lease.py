"""The lease: one holder of the live session at a time, enforced rather than agreed.

    automation ──pause──► awaiting_operator ──take──► operator_in_control
         ▲                      │ timeout                      │ resume
         └──────── resuming ◄───┴──────────────────────────────┘

The handoffs that use it, against the running app, are tests/app/test_handoff.py.
"""

import pytest

from cua.replay.handoff import (
    AUTOMATION,
    AWAITING_OPERATOR,
    OPERATOR_IN_CONTROL,
    Control,
    ControlError,
)


def test_only_the_holder_may_act():
    control = Control()
    control.assert_may_act("automation")
    with pytest.raises(ControlError):
        control.assert_may_act("operator")


def test_control_moves_only_along_declared_transitions():
    control = Control()
    control.move(AWAITING_OPERATOR, "operator")
    with pytest.raises(ControlError):
        control.move(AUTOMATION, "automation")      # must pass through the Operator
    control.move(OPERATOR_IN_CONTROL, "operator")
    with pytest.raises(ControlError):
        control.assert_may_act("automation")        # they cannot both hold it
