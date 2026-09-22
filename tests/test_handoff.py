"""Control transfer: one holder at a time, the same session, and a checked resume."""

import json
from pathlib import Path

import pytest

from cua.artifact import AppProfile, Artifact, merged
from cua.engine import RunContext, replay
from cua.handoff import (AUTOMATION, AWAITING_OPERATOR, OPERATOR_IN_CONTROL, Control,
                         ControlError)

from .fixtures import app_profile_dict, artifact_dict

EXPIRY_MEMBER = "88888"
INPUTS = {"member_number": EXPIRY_MEMBER, "account_type": "savings", "nickname": "After handoff"}


@pytest.fixture
def artifact():
    return merged(Artifact.model_validate(artifact_dict()),
                  AppProfile.model_validate(app_profile_dict()))


def operator_signs_back_in(request, surface):
    """A person doing by hand what the automation may not: re-authenticate.

    They act on the session the automation was already using — same browser, same
    page — which is the point of the seam.
    """
    tb = surface.page.get_by_role("textbox")
    tb.nth(0).fill("svc_officer")
    tb.nth(1).fill("officer-pw")
    surface.page.get_by_role("button", name="Sign in").click()
    surface.page.wait_for_load_state()
    return "resume"


def operator_gives_up(request, surface):
    return "abort"


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
    r = replay(artifact, INPUTS, RunContext(origin=bank_app, attended=True,
                                            operator=operator_signs_back_in,
                                            evidence_root=str(tmp_path)))
    assert r.status == "succeeded", r
    events = [e["event"] for e in r.trail]
    assert "intervention_raised" in events
    assert "operator_acted" in events
    assert "resumed" in events


def test_the_intervention_carries_enough_context_to_act_on(artifact, bank_app, tmp_path):
    replay(artifact, INPUTS, RunContext(origin=bank_app, attended=True,
                                        operator=operator_signs_back_in,
                                        evidence_root=str(tmp_path)))
    request = json.loads(next(tmp_path.rglob("intervention.json")).read_text())
    assert request["capability"] == "member.open_sub_account"
    assert request["watcher"] == "w_session_expired"
    assert request["reason"]
    assert request["url"] and Path(request["screenshot"]).exists()


def test_what_the_operator_did_is_recorded_without_what_they_typed(artifact, bank_app, tmp_path):
    r = replay(artifact, INPUTS, RunContext(origin=bank_app, attended=True,
                                            operator=operator_signs_back_in,
                                            evidence_root=str(tmp_path)))
    acted = next(e for e in r.trail if e["event"] == "operator_acted")
    assert acted["decision"] == "resume"
    assert acted["navigated"] is True
    body = (Path(r.evidence_id) / "trail.jsonl").read_text()
    assert "officer-pw" not in body


def test_an_operator_may_abort_and_that_is_not_a_failure(artifact, bank_app, tmp_path):
    r = replay(artifact, INPUTS, RunContext(origin=bank_app, attended=True,
                                            operator=operator_gives_up,
                                            evidence_root=str(tmp_path)))
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

    r = replay(artifact, INPUTS, RunContext(origin=bank_app, attended=True,
                                            operator=wanders_off,
                                            evidence_root=str(tmp_path)))
    assert r.status == "failed"
    assert r.reason in ("resume_checkpoint_missed", "escalation_budget_exhausted")
