"""A commit nobody could confirm is Outcome Unknown, not Failed.

S1 of the architecture review. Failed invites a retry; Outcome Unknown means a person
must look before anything is tried again. The difference is decided by which
Checkpoint failed — before the action, or after it — and by whether a Verification
Check could settle the question. The pure half, the trail reader, is in
tests/unit/test_recovery.py.
"""

from copy import deepcopy

from cua.domain.artifact import Artifact, merged
from cua.governance.profile import load_profile
from cua.replay.engine import RunContext, replay
from tests.support.artifact import artifact_dict
from tests.support.doubles import approves, approves_then_aborts, attended

VENDOR_APP = "demo-core-servicing"


def unverifiable(base):
    """The same Artifact with the Verification Check taken off its commit.

    Every run of a committing capability is attended, and this is the case where the
    effect can still end up unconfirmed: the person approved the commit, and nobody
    can say afterwards whether it took.
    """
    doc = deepcopy(base)
    for t in doc["transitions"]:
        if t["risk"] == "consequential":
            t.pop("verify_effect", None)
    return merged(Artifact.model_validate(doc), load_profile(VENDOR_APP))


def test_an_unconfirmable_commit_returns_outcome_unknown_not_failed(bank_app, tmp_path):
    """33333 holds the maximum, so the commit lands on a screen no Watcher knows.

    With no Verification Check there is nothing that can say whether it took effect.
    The Operator approved the commit, then nobody answers the escalation, so the run
    ends without ever settling the question — and Failed would invite the caller to
    try the commit again.
    """
    art = unverifiable(artifact_dict())
    r = replay(art, {"member_number": "33333", "account_type": "savings",
                     "nickname": "Unconfirmable"},
               RunContext(origin=bank_app, attended=True, operator=approves,
                          operator_timeout_s=1.5, evidence_root=str(tmp_path)))
    assert r.status == "outcome_unknown", r
    assert "do not retry" in r.reason
    assert r.step == "review_shown"


def test_an_operator_who_aborts_after_a_commit_is_an_abort_not_a_guess(bank_app, tmp_path):
    """A person chose to stop; that is a decision, not an unconfirmed effect."""
    art = unverifiable(artifact_dict())
    r = replay(art, {"member_number": "33333", "account_type": "savings",
                     "nickname": "Unconfirmable"},
               RunContext(origin=bank_app, attended=True, operator=approves_then_aborts,
                          evidence_root=str(tmp_path)))
    assert r.status == "aborted", r


def test_a_safe_step_that_times_out_is_a_failure_not_outcome_unknown(artifact, bank_app,
                                                                     tmp_path):
    """44444 escalates on a safe click: nothing was committed, so nothing is in doubt."""
    r = replay(artifact, {"member_number": "44444", "account_type": "savings",
                          "nickname": "Flagged"},
               RunContext(origin=bank_app, attended=True, operator=None,
                          operator_timeout_s=1.5, evidence_root=str(tmp_path)))
    assert r.status == "failed"
    assert r.reason == "escalation_timeout"


def test_a_settled_negative_is_still_a_plain_failure(artifact, bank_app):
    """The Verification Check looked and said no: that is not Outcome Unknown."""
    r = replay(artifact, {"member_number": "33333", "account_type": "savings",
                          "nickname": "Holiday fund"}, RunContext(origin=bank_app, **attended()))
    assert r.status == "failed"
    assert r.verified_effect is False


def test_a_precondition_that_never_held_is_a_failure_not_outcome_unknown(artifact, bank_app):
    """Nothing was done, so nothing is in doubt."""
    r = replay(artifact, {"member_number": "44444", "account_type": "savings",
                          "nickname": "Flagged"},
               RunContext(origin=bank_app, operator_timeout_s=1.5, **attended()))
    assert r.status == "failed"
