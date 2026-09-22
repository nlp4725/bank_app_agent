"""The guardrails, and the tests that are themselves controls.

Permissions are Baseline ∩ Role ∩ Tenant grant ∩ Needs; the first three are files
owned by different people, and the fourth is derived from what a run actually did.
"""

import ast
import json
from pathlib import Path

import pytest

from cua.artifact import AppProfile, Artifact, merged
from cua.profile import load_profile
from cua.engine import RunContext, replay
from cua.policy import Policy, load_baseline, load_tenant_policy

from .fixtures import artifact_dict

INPUTS = {"member_number": "12345", "account_type": "savings", "nickname": "Holiday fund"}
CUA = Path(__file__).resolve().parent.parent / "cua"


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


MODEL_SDKS = {"anthropic", "openai", "google", "litellm"}


def module_graph(entry: str) -> set[str]:
    """Every cua module reachable from `entry`, transitively."""
    seen, queue = set(), [entry]
    while queue:
        name = queue.pop()
        if name in seen:
            continue
        seen.add(name)
        path = CUA / f"{name}.py"
        if not path.exists():
            continue
        for imported in imports_of(path):
            if (CUA / f"{imported}.py").exists():
                queue.append(imported)
    return seen


def test_replay_cannot_reach_a_model_sdk():
    """Not 'no file imports it' — the replay path cannot reach it, transitively."""
    for name in module_graph("engine"):
        assert not (imports_of(CUA / f"{name}.py") & MODEL_SDKS), \
            f"replay reaches {name}.py, which imports a model SDK"


def test_the_model_sdk_lives_only_in_discovery():
    users = {p.stem for p in CUA.glob("*.py") if imports_of(p) & MODEL_SDKS}
    assert users == {"discovery"}, f"unexpected model SDK users: {users}"


def test_discovery_is_not_reachable_from_replay():
    assert "discovery" not in module_graph("engine")


def test_only_the_surface_module_touches_playwright():
    for path in CUA.glob("*.py"):
        if path.name == "surface.py":
            continue
        assert "playwright" not in imports_of(path), f"{path.name} imports playwright"


# ── the Surface seam: two interfaces, and nothing reaching past them ──────────

ACTING = {"origin", "allowed_origins", "blocked_requests", "url", "goto", "text",
          "wait", "close", "screenshot", "resolve", "click", "type", "select",
          "read", "value_of", "frame_urls"}


def _attributes_used_on(path, variable):
    """Every `variable.X` in a module, statically."""
    import ast
    tree = ast.parse(Path(path).read_text())
    return {n.attr for n in ast.walk(tree)
            if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name)
            and n.value.id == variable}


def test_the_replay_path_uses_only_the_acting_interface():
    """Not 'it happens to work' — the engine may not reach for a driver object.

    This is the assertion that makes a scripted Surface possible: the engine used to
    read `surface.page.frames` and call the private `_tick`.
    """
    used = _attributes_used_on(CUA / "engine.py", "surface")
    assert used <= ACTING, f"the engine reaches past the acting interface: {used - ACTING}"


def test_the_predicate_evaluator_needs_only_four_observations():
    used = _attributes_used_on(CUA / "predicates.py", "surface")
    assert used <= {"text", "url", "resolve", "value_of", "wait", "goto"}, used


def test_the_recording_interface_does_not_offer_the_acting_one():
    """A Discovery Run enumerates and describes; it does not get a driver handle."""
    from cua.surface import RecordingSurface
    for name in ("resolve", "click", "type", "select", "read", "value_of", "page"):
        assert not hasattr(RecordingSurface, name), \
            f"RecordingSurface exposes {name!r}, so the union interface is back"


def test_discovery_acts_through_the_recording_interface_not_on_a_locator():
    used = _attributes_used_on(CUA / "discovery.py", "surface")
    assert "act_on" in used
    assert not ({"click", "type", "select", "read", "page"} & used), used
