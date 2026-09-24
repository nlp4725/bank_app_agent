"""Control transfer: one holder at a time, the same session, and a checked resume."""

import json
from pathlib import Path

import pytest

from cua.domain.artifact import AppProfile, Artifact, merged
from cua.governance.profile import load_profile
from cua.replay.engine import RunContext, replay
from cua.replay.handoff import (AUTOMATION, AWAITING_OPERATOR, OPERATOR_IN_CONTROL, Control,
                         ControlError)

from .fixtures import artifact_dict

# The flagged member: only a supervisor's own ID and PIN clears it, and no Role
# holds those, so this is the one condition a person must resolve inside the run.
FLAGGED_MEMBER = "44444"
INPUTS = {"member_number": FLAGGED_MEMBER, "account_type": "savings", "nickname": "After handoff"}


def operator_clears_the_flag(request, surface):
    """A person doing by hand what the automation may not: sign off as themselves.

    They act on the session the automation was already using — same browser, same
    page — which is the point of the seam. The supervisor PIN belongs to them, not
    to any Service Account, so no Role could have typed it.
    """
    tb = surface.page.get_by_role("textbox")
    tb.nth(0).fill("sup_ramirez")
    tb.nth(1).fill("4821")
    surface.page.get_by_role("button", name="Acknowledge").click()
    surface.page.wait_for_load_state()
    return "resume"


def operator_gives_up(request, surface):
    return "abort"


def escalating_run(artifact, bank_app, tmp_path, operator, **overrides):
    """A run on the flagged member, with an Operator on shift."""
    return replay(artifact, INPUTS,
                  RunContext(origin=bank_app, attended=True, operator=operator,
                             evidence_root=str(tmp_path), **overrides))


# ── the lease ────────────────────────────────────────────────────────────────

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


# ── the whole handoff, against the live app ─────────────────────────────────

def test_an_operator_takes_the_live_session_and_the_run_completes(artifact, bank_app, tmp_path):
    r = escalating_run(artifact, bank_app, tmp_path, operator_clears_the_flag)
    assert r.status == "succeeded", r
    events = [e["event"] for e in r.trail]
    assert "intervention_raised" in events
    assert "operator_acted" in events
    assert "resumed" in events


def test_the_intervention_carries_enough_context_to_act_on(artifact, bank_app, tmp_path):
    escalating_run(artifact, bank_app, tmp_path, operator_clears_the_flag)
    request = json.loads(next(tmp_path.rglob("intervention.json")).read_text())
    assert request["capability"] == "member.open_sub_account"
    assert request["watcher"] == "w_approval_required"
    assert request["reason"]
    assert request["instruction"]
    assert request["url"] and Path(request["screenshot"]).exists()


def test_what_the_operator_did_is_recorded_without_what_they_typed(artifact, bank_app, tmp_path):
    r = escalating_run(artifact, bank_app, tmp_path, operator_clears_the_flag)
    acted = next(e for e in r.trail if e["event"] == "operator_acted")
    assert acted["decision"] == "resume"
    assert acted["navigated"] is True
    body = (Path(r.evidence_id) / "trail.jsonl").read_text()
    assert "officer-pw" not in body        # the automation's secret
    assert "4821" not in body              # and the Operator's own PIN


def test_an_operator_may_abort_and_that_is_not_a_failure(artifact, bank_app, tmp_path):
    r = escalating_run(artifact, bank_app, tmp_path, operator_gives_up)
    assert r.status == "aborted"
    assert "operator" in r.reason


def test_an_unanswered_intervention_times_out_rather_than_hanging(artifact, bank_app, tmp_path):
    r = replay(artifact, INPUTS, RunContext(origin=bank_app, attended=True,
                                            operator=None, operator_timeout_s=1.5,
                                            evidence_root=str(tmp_path)))
    assert r.status == "failed"
    assert r.reason == "escalation_timeout"


def test_resume_re_checks_where_it_is_rather_than_assuming(artifact, bank_app, tmp_path):
    """An Operator who wanders off leaves the run somewhere it cannot continue."""
    def wanders_off(request, surface):
        surface.goto("/admin")
        return "resume"

    r = escalating_run(artifact, bank_app, tmp_path, wanders_off)
    assert r.status == "failed"
    assert r.reason in ("resume_checkpoint_missed", "escalation_budget_exhausted")
