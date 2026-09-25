"""The App Profile has one home: config/profiles/<app>.yaml, read through load_profile. What it declares readable and sensitive is data a Reviewer owns."""

import pytest

from cua.governance.profile import UnknownProfile, load_profile

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


# ── declared regions live in the App Profile, reviewable as data ─────────────

def test_readable_regions_are_declared_on_the_app_profile():
    profile = load_profile("demo-core-servicing")
    assert "t_balance" in profile.readable_regions
    assert "t_member_name" not in profile.readable_regions


# ── the two channels take opposite defaults, on purpose ──────────────────────

def test_values_are_allowlisted_but_pixels_are_deny_listed():
    profile = load_profile("demo-core-servicing")
    assert profile.readable_regions == ["t_balance", "t_new_number"]
    assert profile.sensitive_regions == ["t_member_name", "t_member_since"]
    # a control the model must use is readable in pixels though its value is hidden
    assert "t_ok" not in profile.sensitive_regions
    assert "t_ok" not in profile.readable_regions
