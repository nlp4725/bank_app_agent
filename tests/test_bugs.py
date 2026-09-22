"""The three defects an architecture review surfaced, and the tests that hold them shut.

Each one was a guarantee the design documents state and the code did not keep.
"""

import json
from copy import deepcopy
from pathlib import Path

import pytest

from cua.artifact import Artifact, merged
from cua.engine import RunContext, replay
from cua.evidence import unfinished
from cua.policy import Policy, load_baseline, policy_for
from cua.profile import load_profile

from .fixtures import artifact_dict

VENDOR_APP = "demo-core-servicing"


# ── S3: Baseline ∩ Role ∩ Tenant — every layer narrows, none widens ──────────

def _policy(tenant_doc, role="balance_reader"):
    return Policy(baseline=load_baseline(), tenant=tenant_doc,
                  role_name=role, vendor_app=VENDOR_APP)


def test_a_tenant_cannot_grant_a_route_its_role_does_not_hold():
    """The inversion: the tenant's list used to replace the role's, not narrow it."""
    greedy = {"tenant": "greedy", "origin": "http://x",
              "roles_granted": {"balance_reader": {}},
              "pages": ["/login", "/members/*", "/vault/*"]}
    policy = _policy(greedy)
    assert policy.allows_page("/members/12345")
    assert not policy.allows_page("/vault/gold"), \
        "a tenant policy widened the role it was granted"


def test_a_tenant_may_still_narrow_its_role():
    narrow = {"tenant": "careful", "origin": "http://x",
              "roles_granted": {"balance_reader": {}},
              "pages": ["/login"]}
    policy = _policy(narrow)
    assert policy.allows_page("/login")
    assert not policy.allows_page("/members/12345")


def test_a_tenant_that_narrows_nothing_gets_exactly_its_role():
    plain = {"tenant": "plain", "origin": "http://x",
             "roles_granted": {"balance_reader": {}}}
    policy = _policy(plain)
    assert policy.allows_page("/members/12345")
    assert not policy.allows_page("/transfers/new")


def test_the_baseline_still_refuses_what_every_layer_above_allowed():
    everything = {"tenant": "loose", "origin": "http://x",
                  "roles_granted": {"funds_mover": {}},
                  "pages": ["/transfers/*"]}
    assert not _policy(everything, "funds_mover").allows_page("/transfers/new")


# ── S4: the Allowlist covers origins, not only routes ────────────────────────

def test_an_undeclared_origin_is_refused_before_the_browser_opens(artifact, bank_app):
    r = replay(artifact, {"member_number": "12345", "account_type": "savings",
                          "nickname": "Elsewhere"},
               RunContext(origin="http://127.0.0.1:9999", tenant="bank_a"))
    assert r.status == "refused"
    assert "origin" in r.reason
    assert r.trail, "a refusal still leaves evidence"


def test_a_declared_origin_runs(artifact, bank_app):
    """The test harness's instance is declared in the tenant's own policy file."""
    policy = policy_for(artifact, "bank_a")
    assert policy.allows_origin(bank_app)
    r = replay(artifact, {"member_number": "12345", "account_type": "savings",
                          "nickname": "Declared"}, RunContext(origin=bank_app))
    assert r.status == "succeeded", r


def test_the_origin_comes_from_the_tenant_not_from_whichever_tool_is_running():
    from cua.store import origin_for
    policy_origin = origin_for("bank_a", VENDOR_APP)
    assert policy_origin in policy_for(_Shim(), "bank_a").origins()


class _Shim:
    capability = type("c", (), {"vendor_app": VENDOR_APP, "role": "balance_reader"})()


# ── S1: a commit nobody could confirm is Outcome Unknown, not Failed ─────────

def unverifiable(base):
    """The same Artifact with the Verification Check taken off its commit.

    Allowed only in an Attended run — the front door refuses it unattended — which is
    exactly the case where the effect can end up unconfirmed.
    """
    doc = deepcopy(base)
    for t in doc["transitions"]:
        if t["risk"] == "consequential":
            t.pop("verify_effect", None)
    return merged(Artifact.model_validate(doc), load_profile(VENDOR_APP))


def test_an_unconfirmable_commit_returns_outcome_unknown_not_failed(bank_app, tmp_path):
    """33333 holds the maximum, so the commit lands on a screen no Watcher knows.

    With no Verification Check there is nothing that can say whether it took effect.
    Nobody answers the escalation, so the run ends without ever settling the
    question — and Failed would invite the caller to try the commit again.
    """
    art = unverifiable(artifact_dict())
    r = replay(art, {"member_number": "33333", "account_type": "savings",
                     "nickname": "Unconfirmable"},
               RunContext(origin=bank_app, attended=True, operator=None,
                          operator_timeout_s=1.5, evidence_root=str(tmp_path)))
    assert r.status == "outcome_unknown", r
    assert "do not retry" in r.reason
    assert r.step == "review_shown"


def test_an_operator_who_aborts_after_a_commit_is_an_abort_not_a_guess(bank_app, tmp_path):
    """A person chose to stop; that is a decision, not an unconfirmed effect."""
    art = unverifiable(artifact_dict())
    r = replay(art, {"member_number": "33333", "account_type": "savings",
                     "nickname": "Unconfirmable"},
               RunContext(origin=bank_app, attended=True, operator=lambda rq, s: "abort",
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
                          "nickname": "Holiday fund"}, RunContext(origin=bank_app))
    assert r.status == "failed"
    assert r.verified_effect is False


def test_a_precondition_that_never_held_is_a_failure_not_outcome_unknown(artifact, bank_app):
    """Nothing was done, so nothing is in doubt."""
    r = replay(artifact, {"member_number": "44444", "account_type": "savings",
                          "nickname": "Flagged"}, RunContext(origin=bank_app))
    assert r.status == "failed"


# ── S1: the write-ahead log detects a death mid-commit ───────────────────────

def write_trail(directory, lines):
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "trail.jsonl").write_text("\n".join(json.dumps(l) for l in lines))


def test_a_run_that_died_mid_commit_is_found_on_restart(tmp_path):
    write_trail(tmp_path / "run_dead", [
        {"run_id": "run_dead", "event": "about_to", "step": "review_shown",
         "action": "click", "target": "t_commit", "risk": "consequential"},
    ])
    found = unfinished(tmp_path)
    assert len(found) == 1
    assert found[0]["status"] == "outcome_unknown"
    assert found[0]["step"] == "review_shown"


def test_a_run_that_finished_its_commit_is_not_reported(tmp_path):
    write_trail(tmp_path / "run_ok", [
        {"run_id": "run_ok", "event": "about_to", "step": "review_shown",
         "action": "click", "target": "t_commit", "risk": "consequential"},
        {"run_id": "run_ok", "event": "done", "step": "review_shown"},
        {"run_id": "run_ok", "event": "result", "status": "succeeded"},
    ])
    assert unfinished(tmp_path) == []


def test_a_run_that_died_before_anything_consequential_is_not_reported(tmp_path):
    write_trail(tmp_path / "run_early", [
        {"run_id": "run_early", "event": "about_to", "step": "sign_in",
         "action": "type", "target": "t_user", "risk": "safe"},
    ])
    assert unfinished(tmp_path) == []


def test_a_real_run_leaves_a_trail_the_detector_reads(artifact, bank_app, tmp_path):
    replay(artifact, {"member_number": "12345", "account_type": "savings",
                      "nickname": "Holiday fund"},
           RunContext(origin=bank_app, evidence_root=str(tmp_path)))
    assert unfinished(tmp_path) == [], "a completed run must not look unfinished"
