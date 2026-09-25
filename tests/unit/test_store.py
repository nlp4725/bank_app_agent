"""The Capability Store: one answer to "which Artifact is live?".

These are the tests that were missing while the repo carried two models of one
capability — the hand-written fixture and the approved file — with nothing
comparing them, so a discovery literal could sit inside the shipped Artifact
unnoticed.
"""

from pathlib import Path

import pytest

from cua.authoring.lint import lint
from cua.governance.profile import UnknownProfile, load_profile
from cua.governance.store import UnknownCapability, load_capability, origin_for, overlay_for

CAPABILITY = "member.open_sub_account"
VENDOR_APP = "demo-core-servicing"


# ── the App Profile has one home ─────────────────────────────────────────────

def test_the_app_profile_is_read_from_config_not_from_a_fixture():
    profile = load_profile(VENDOR_APP)
    assert profile.app_profile == VENDOR_APP
    assert {w.id for w in profile.watchers} >= {"w_session_expired", "w_approval_required"}


def test_an_unknown_vendor_app_has_no_profile():
    with pytest.raises(UnknownProfile):
        load_profile("no-such-app")


def test_the_test_package_no_longer_holds_an_app_profile():
    from tests.support import artifact as fixtures
    assert not hasattr(fixtures, "app_profile_dict")


# ── the Store ────────────────────────────────────────────────────────────────

def test_the_store_answers_with_the_approved_artifact_and_its_profile():
    art = load_capability(CAPABILITY)
    assert art.capability.status == "approved"
    assert len(art.capability.approvals) >= 2
    # merged, so the app-wide Watchers arrived without the caller asking
    assert {w.id for w in art.watchers} >= {"w_session_expired", "w_app_error"}


def test_a_draft_never_displaces_an_approved_artifact_of_the_same_version():
    """Both files carry 1.0.0; re-reviewing in place must not change what replays."""
    assert load_capability(CAPABILITY).capability.status == "approved"


def test_an_unknown_capability_is_named_rather_than_guessed():
    with pytest.raises(UnknownCapability):
        load_capability("member.not_a_capability")


def test_the_tenant_address_comes_from_the_tenant_s_own_policy():
    assert origin_for("bank_a", VENDOR_APP).endswith(":5001")
    assert origin_for("lakeside", VENDOR_APP).endswith(":5002")


def test_a_tenant_without_an_overlay_gets_none_rather_than_an_empty_patch():
    assert overlay_for("bank_a") is None
    assert overlay_for("lakeside")["tenant"] == "lakeside"


# ── the artifact that actually ships ─────────────────────────────────────────

def test_the_shipped_artifact_lints_clean():
    issues = [str(i) for i in lint(load_capability(CAPABILITY), unattended=False)]
    assert issues == [], issues


def test_no_discovery_value_survived_into_the_shipped_artifact():
    """The case this missed before: the model picked the option's visible label
    ("Savings") while the Contract names its value ("savings")."""
    art = load_capability(CAPABILITY)
    selects = [t for t in art.transitions if t.action.type == "select"]
    assert selects, "the flow no longer selects an account type"
    for t in selects:
        assert t.action.value.startswith("{{"), \
            f"{t.action.value!r} is a literal, not an input"


def test_every_target_asset_the_shipped_artifact_names_exists():
    """A picture rung pinned to a run directory dies when runs/ is pruned."""
    from pathlib import Path
    art = load_capability(CAPABILITY)
    for name, target in art.targets.items():
        for rung in target.rungs:
            if rung.kind == "picture":
                assert not rung.asset.startswith("runs/"), \
                    f"{name} pins its picture rung to a run directory"
                assert Path(rung.asset).exists(), f"{name}: missing {rung.asset}"


# ── the Recorder must never name an asset that is not there ──────────────────

def test_a_run_compiled_after_it_moved_still_finds_its_crops(tmp_path):
    """`actions.json` records the crop path the run had when it was written. Copy the
    run — into evidence/, or onto another machine — and that path is gone, but the
    crops travelled with it in screens/."""
    import json
    import shutil

    from cua.authoring.recorder import record_from_run
    from tools.discovery.cli import CONTRACT

    moved = tmp_path / "somewhere_else"
    shutil.copytree("evidence/01-discovery-goal-reached", moved)
    actions = json.loads((moved / "actions.json").read_text())
    assert any(a.get("crop", "").startswith("runs/") for a in actions), \
        "this run no longer records crops by a stale path; the test has nothing to prove"

    draft, _ = record_from_run(
        str(moved), CONTRACT,
        {"member_number": "54321", "account_type": "savings", "nickname": "Holiday fund"},
        capability_id="member.test_moved", vendor_app="demo-core-servicing",
        role="account_opener", assets_dir=tmp_path / "assets")

    pictures = [r for t in draft["targets"].values() for r in t["rungs"]
                if r["kind"] == "picture"]
    assert pictures, "the crops were beside the run and should have been found"
    for rung in pictures:
        assert Path(rung["asset"]).exists(), f"named a missing asset: {rung['asset']}"


def test_a_missing_crop_drops_the_rung_rather_than_naming_a_dead_file(tmp_path):
    """A ladder that claims a fallback it does not have is worse than a short ladder."""
    from cua.authoring.recorder import record
    actions = [{"turn": 1, "action": "click", "role": "button", "name": "Sign in",
                "anchor": None, "target": {"rungs": [{"kind": "role_name",
                                                      "role": "button", "name": "Sign in"}]},
                "crop": "nowhere/at/all.png",
                "url_before": "http://x/login", "url_after": "http://x/search"}]
    draft, suggestions = record(actions, {"inputs": {}, "outputs": {}, "outcomes": []}, {},
                                capability_id="member.test_missing",
                                vendor_app="demo-core-servicing", role="account_opener",
                                assets_dir=tmp_path / "assets")
    rungs = [r for t in draft["targets"].values() for r in t["rungs"]]
    assert not any(r["kind"] == "picture" for r in rungs)
    assert any("crop" in s and "missing" in s for s in suggestions)
