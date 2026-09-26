"""The lease: one holder of the live session at a time, enforced rather than agreed.

    automation ──pause──► awaiting_operator ──take──► operator_in_control
         ▲                      │ timeout                      │ resume
         └──────── resuming ◄───┴──────────────────────────────┘

The handoffs that use it, against the running app, are tests/app/test_handoff.py.
"""

import json
import time

import pytest

from cua.replay.handoff import (
    AUTOMATION,
    AWAITING_OPERATOR,
    OPERATOR_IN_CONTROL,
    STALE_AFTER_S,
    Control,
    ControlError,
    open_requests,
    waiting_request,
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


# ── which request is an Operator being asked? ───────────────────────────────
# A finished run's approval.json stays on disk as evidence, and decision.json is
# deleted once the run reads it, so "a request with no decision beside it" matched
# every attended run ever made. The console then showed a stale request and sent
# the Operator's abort to a run that had already finished.

def _run(root, name, events, request_file="approval.json"):
    d = root / name
    d.mkdir(parents=True)
    (d / "trail.jsonl").write_text("".join(json.dumps({"event": e}) + "\n" for e in events))
    (d / request_file).write_text("{}")
    return d


def test_a_finished_runs_request_is_not_waiting(tmp_path):
    _run(tmp_path, "run_done", ["approval_requested", "operator_acted", "approved", "result"])
    _run(tmp_path, "run_timed_out", ["intervention_raised", "operator_acted", "result"],
         "intervention.json")
    assert open_requests(tmp_path) == []


def test_only_the_run_still_waiting_is_offered(tmp_path):
    _run(tmp_path, "run_done", ["approval_requested", "operator_acted", "result"])
    live = _run(tmp_path, "run_live", ["about_to", "intervention_raised"], "intervention.json")
    assert open_requests(tmp_path) == [live / "intervention.json"]


def test_an_answered_approval_then_a_new_escalation_offers_the_escalation(tmp_path):
    d = _run(tmp_path, "run_x", ["approval_requested", "operator_acted", "approved",
                                 "intervention_raised"], "intervention.json")
    (d / "approval.json").write_text("{}")
    assert waiting_request(d) == d / "intervention.json"


def test_a_decision_not_yet_read_closes_the_request(tmp_path):
    d = _run(tmp_path, "run_x", ["approval_requested"])
    (d / "decision.json").write_text('{"decision": "abort"}')
    assert waiting_request(d) is None


def test_a_run_killed_while_waiting_goes_stale(tmp_path):
    d = _run(tmp_path, "run_x", ["approval_requested"])
    later = time.time() + STALE_AFTER_S + 1
    assert waiting_request(d, now=later) is None
