"""The guardrails, against the live app: refused at the front door, denied mid-run,
masked in the evidence.

The pure half of what this file held — policy layering without a browser, and the
tests that are themselves controls over the import graph — is in
tests/unit/test_policy.py and tests/unit/test_boundaries.py.

Permissions are Baseline ∩ Role ∩ Tenant grant ∩ Needs; the first three are files
owned by different people, and the fourth is derived from what a run actually did.
"""

import json
from pathlib import Path

from cua.domain.artifact import Artifact, merged
from cua.governance.profile import load_profile
from cua.replay.engine import RunContext, replay
from tests.support.artifact import artifact_dict

INPUTS = {"member_number": "12345", "account_type": "savings", "nickname": "Holiday fund"}


# ── the front door ────────────────────────────────────────────────────────────

def test_a_capability_whose_role_the_tenant_has_not_granted_is_refused(artifact, bank_app):
    r = replay(artifact, INPUTS, RunContext(origin=bank_app, tenant="bank_b"))
    assert r.status == "refused"
    assert "account_opener" in r.reason


def test_needs_outside_the_tenants_grant_are_refused(artifact, bank_app):
    d = artifact_dict()
    d["needs"]["pages"] = d["needs"]["pages"] + ["/transfers/*"]
    art = merged(Artifact.model_validate(d), load_profile("demo-core-servicing"))
    r = replay(art, INPUTS, RunContext(origin=bank_app))
    assert r.status == "refused"
    assert "/transfers/*" in r.reason


def test_an_action_type_the_baseline_forbids_is_refused(artifact, bank_app):
    d = artifact_dict()
    d["needs"]["actions"] = d["needs"]["actions"] + ["download"]
    art = merged(Artifact.model_validate(d), load_profile("demo-core-servicing"))
    r = replay(art, INPUTS, RunContext(origin=bank_app))
    assert r.status == "refused"
    assert "download" in r.reason


def test_the_refusal_names_the_layer_that_refused(artifact, bank_app):
    r = replay(artifact, INPUTS, RunContext(origin=bank_app, tenant="bank_b"))
    assert "tenant" in r.reason.lower()


# ── mid-run enforcement ───────────────────────────────────────────────────────

def test_a_request_to_another_origin_is_aborted_in_the_browser(bank_app):
    """The page, not us, starts this one: an <img> pointing off-site.

    A check before we act cannot see it, so the allowlist is enforced on every
    request the browser makes.
    """
    from cua.surface import Surface
    surface = Surface(bank_app)
    try:
        surface.goto("/leaky")
        surface.page.wait_for_timeout(800)
        blocked = surface.blocked_requests
        assert any("attacker.example" in url for url in blocked), blocked
    finally:
        surface.close()


# ── redaction ─────────────────────────────────────────────────────────────────

def test_the_balance_reaches_the_caller_in_full_and_the_record_masked(artifact, bank_app, tmp_path):
    r = replay(artifact, INPUTS, RunContext(origin=bank_app, evidence_root=str(tmp_path)))
    assert r.outputs["savings_balance"] == "$4210.00"        # the answer is the product
    written = (Path(r.evidence_id) / "trail.jsonl").read_text()
    assert "$4210.00" not in written                          # the record of it is not


def test_no_secret_value_appears_anywhere_in_the_evidence(artifact, bank_app, tmp_path):
    r = replay(artifact, INPUTS, RunContext(origin=bank_app, evidence_root=str(tmp_path)))
    for path in Path(r.evidence_id).rglob("*"):
        if path.is_file() and path.suffix in (".jsonl", ".json", ".txt"):
            body = path.read_text()
            assert "officer-pw" not in body
            assert "svc_officer" not in body


def test_every_policy_decision_is_recorded(artifact, bank_app, tmp_path):
    r = replay(artifact, INPUTS, RunContext(origin=bank_app, evidence_root=str(tmp_path)))
    decisions = [json.loads(line) for line in
                 (Path(r.evidence_id) / "trail.jsonl").read_text().splitlines()]
    assert any(d["event"] == "policy_allow" for d in decisions)
