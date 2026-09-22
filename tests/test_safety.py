"""The guardrails, and the tests that are themselves controls.

Permissions are Baseline ∩ Role ∩ Tenant grant ∩ Needs; the first three are files
owned by different people, and the fourth is derived from what a run actually did.
"""

import ast
import json
from pathlib import Path

import pytest

from cua.artifact import AppProfile, Artifact, merged
from cua.engine import RunContext, replay
from cua.policy import Policy, load_baseline, load_tenant_policy

from .fixtures import app_profile_dict, artifact_dict

INPUTS = {"member_number": "12345", "account_type": "savings", "nickname": "Holiday fund"}
CUA = Path(__file__).resolve().parent.parent / "cua"


@pytest.fixture
def artifact():
    return merged(Artifact.model_validate(artifact_dict()),
                  AppProfile.model_validate(app_profile_dict()))


# ── the front door ────────────────────────────────────────────────────────────

def test_a_capability_whose_role_the_tenant_has_not_granted_is_refused(artifact, bank_app):
    r = replay(artifact, INPUTS, RunContext(origin=bank_app, tenant="bank_b"))
    assert r.status == "refused"
    assert "account_opener" in r.reason


def test_needs_outside_the_tenants_grant_are_refused(artifact, bank_app):
    d = artifact_dict()
    d["needs"]["pages"] = d["needs"]["pages"] + ["/transfers/*"]
    art = merged(Artifact.model_validate(d), AppProfile.model_validate(app_profile_dict()))
    r = replay(art, INPUTS, RunContext(origin=bank_app))
    assert r.status == "refused"
    assert "/transfers/*" in r.reason


def test_an_action_type_the_baseline_forbids_is_refused(artifact, bank_app):
    d = artifact_dict()
    d["needs"]["actions"] = d["needs"]["actions"] + ["download"]
    art = merged(Artifact.model_validate(d), AppProfile.model_validate(app_profile_dict()))
    r = replay(art, INPUTS, RunContext(origin=bank_app))
    assert r.status == "refused"
    assert "download" in r.reason


def test_the_refusal_names_the_layer_that_refused(artifact, bank_app):
    r = replay(artifact, INPUTS, RunContext(origin=bank_app, tenant="bank_b"))
    assert "tenant" in r.reason.lower()


# ── policy layering, without a browser ───────────────────────────────────────

def test_a_tenant_may_narrow_the_baseline_never_widen_it():
    baseline = load_baseline()
    tenant = load_tenant_policy("bank_a", "demo-core-servicing")
    policy = Policy(baseline=baseline, tenant=tenant, role_name="account_opener",
                    vendor_app="demo-core-servicing")
    assert policy.allows_action("click")
    assert not policy.allows_action("download")       # the baseline forbids it
    assert policy.allows_page("/members/12345")
    assert not policy.allows_page("/admin")           # keyword deny plus route allowlist


def test_a_read_only_role_may_not_commit():
    baseline = load_baseline()
    tenant = load_tenant_policy("bank_a", "demo-core-servicing")
    policy = Policy(baseline=baseline, tenant=tenant, role_name="balance_reader",
                    vendor_app="demo-core-servicing")
    assert policy.consequential_allowed() is False
    assert policy.service_account() == "svc_read"


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


# ── tests that are controls ───────────────────────────────────────────────────

def imports_of(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module.split(".")[0])
    return found


def test_replay_cannot_reach_a_model_sdk():
    forbidden = {"anthropic", "openai", "google", "litellm"}
    for path in CUA.glob("*.py"):
        assert not (imports_of(path) & forbidden), f"{path.name} imports a model SDK"


def test_only_the_surface_module_touches_playwright():
    for path in CUA.glob("*.py"):
        if path.name == "surface.py":
            continue
        assert "playwright" not in imports_of(path), f"{path.name} imports playwright"
