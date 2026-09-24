"""Replay, end to end, against the running demo app. No model anywhere.

Each member number selects a scenario, so a test reads as "replay for 99999 and
expect MEMBER_NOT_FOUND" with nothing mocked.
"""


from cua.domain.artifact import Artifact, merged
from cua.governance.profile import load_profile
from cua.replay.engine import RunContext, replay

from .fixtures import artifact_dict

INPUTS = {"member_number": "12345", "account_type": "savings", "nickname": "Holiday fund"}


def run(artifact, bank_app, member=None, attended=False, **overrides):
    inputs = dict(INPUTS, **overrides)
    if member:
        inputs["member_number"] = member
    return replay(artifact, inputs, RunContext(origin=bank_app, attended=attended))


# ── the happy path ────────────────────────────────────────────────────────────

def test_a_normal_member_succeeds_and_returns_both_outputs(artifact, bank_app):
    r = run(artifact, bank_app, "12345")
    assert r.status == "succeeded", r
    assert r.outputs["savings_balance"] == "$4210.00"
    assert r.outputs["new_account_number"].startswith("SA-")


def test_the_same_inputs_give_the_same_result_every_time(artifact, bank_app):
    results = []
    for _ in range(3):
        results.append(run(artifact, bank_app, "12345"))
    assert {r.status for r in results} == {"succeeded"}
    assert {r.outputs["savings_balance"] for r in results} == {"$4210.00"}


def test_replay_records_which_rung_resolved_each_target(artifact, bank_app):
    r = run(artifact, bank_app, "12345")
    rungs = {e["target"]: e["matched_by"] for e in r.trail if e.get("matched_by")}
    assert rungs["t_signin"] == "role_name"          # buttons have accessible names
    assert rungs["t_member_field"] == "label_anchor"  # fields do not
    assert rungs["t_search"] == "label_anchor"        # the unlabelled icon: rung 1 missed


# ── business outcomes: the app answered, and the answer is not the happy one ──

def test_an_unknown_member_is_a_business_outcome_not_a_failure(artifact, bank_app):
    r = run(artifact, bank_app, "99999")
    assert r.status == "business_outcome"
    assert r.outcome["code"] == "MEMBER_NOT_FOUND"
    assert r.outcome["resolver"] == "member"
    assert r.outcome["retry_same_inputs"] == "never"


def test_a_restricted_member_is_a_business_outcome(artifact, bank_app):
    r = run(artifact, bank_app, "22222")
    assert r.status == "business_outcome"
    assert r.outcome["code"] == "NOT_AUTHORIZED"
    assert r.outcome["resolver"] == "institution_staff"


# ── recoverable conditions: fixed inside the run, invisible to the caller ─────

def test_an_interstitial_is_dismissed_and_the_run_completes(artifact, bank_app):
    r = run(artifact, bank_app, "54321")
    assert r.status == "succeeded", r
    assert any(e.get("watcher") == "w_system_notice" for e in r.trail)


def test_a_transient_error_is_retried_and_the_run_completes(artifact, bank_app):
    r = run(artifact, bank_app, "77777")
    assert r.status == "succeeded", r
    assert any(e.get("watcher") == "w_app_error" for e in r.trail)


def test_a_slow_panel_is_waited_out_rather_than_slept_through(artifact, bank_app):
    r = run(artifact, bank_app, "66666")
    assert r.status == "succeeded", r
    assert r.outputs["savings_balance"] == "$44.00"


# ── recovery and escalation ───────────────────────────────────────────────────

def test_an_expired_session_is_signed_into_again_by_the_system(artifact, bank_app):
    """The automation holds this credential, so no person is needed: Recoverable.

    Nothing re-types the password by hand — the run re-observes, finds itself on the
    sign-in screen, and walks the Artifact's own login transitions again.
    """
    r = run(artifact, bank_app, "88888", attended=False)
    assert r.status == "succeeded", r
    events = [e["event"] for e in r.trail]
    assert "watcher_matched" in events
    assert "recovered" in events


def test_a_flagged_member_escalates_and_fails_when_no_operator_is_available(artifact, bank_app):
    """A supervisor ID and PIN belong to a person; no Role holds them."""
    r = run(artifact, bank_app, "44444", attended=False)
    assert r.status == "failed"
    assert r.reason == "escalation_required"
    assert r.watcher == "w_approval_required"


# ── the held-out condition ────────────────────────────────────────────────────

def test_an_unwatched_screen_is_an_unknown_state_not_a_wrong_answer(artifact, bank_app):
    """33333 already holds the maximum; no Watcher covers that screen on purpose."""
    r = run(artifact, bank_app, "33333")
    assert r.status == "failed"
    assert r.reason == "unknown_state"
    assert r.evidence_id


def test_the_verification_check_shows_the_commit_did_not_take_effect(artifact, bank_app):
    r = run(artifact, bank_app, "33333")
    assert r.verified_effect is False       # we looked, rather than clicking again


# ── the front door ────────────────────────────────────────────────────────────

def test_an_input_failing_its_pattern_is_refused_before_the_browser_opens(artifact, bank_app):
    r = run(artifact, bank_app, "abc")
    assert r.status == "refused"
    assert "member_number" in r.reason


def test_a_draft_artifact_is_refused_for_an_unattended_run(artifact, bank_app):
    d = artifact_dict()
    d["capability"]["status"] = "draft"
    draft = merged(Artifact.model_validate(d), load_profile("demo-core-servicing"))
    r = run(draft, bank_app, "12345")
    assert r.status == "refused"
    assert "approved" in r.reason
