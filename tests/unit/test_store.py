"""The Capability Store: one answer to "which Artifact is live?".

These are the tests that were missing while the repo carried two models of one
capability — the hand-written fixture and the approved file — with nothing
comparing them, so a discovery literal could sit inside the shipped Artifact
unnoticed. The Recorder's own tests are tests/unit/test_recorder.py.
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
    art = load_capability(CAPABILITY)
    for name, target in art.targets.items():
        for rung in target.rungs:
            if rung.kind == "picture":
                assert not rung.asset.startswith("runs/"), \
                    f"{name} pins its picture rung to a run directory"
                assert Path(rung.asset).exists(), f"{name}: missing {rung.asset}"
