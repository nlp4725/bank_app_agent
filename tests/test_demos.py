"""The two demonstrations, as tests so they cannot quietly stop working.

B1: a control with no accessible name is found anyway, and the log says how.
B2: one artifact recorded at one institution runs at another with a small Overlay.
"""

import urllib.request

import pytest

from cua.replay.engine import RunContext, replay
from cua.governance.store import load_capability, overlay_for
from cua.surface import Surface

INPUTS = {"member_number": "12345", "account_type": "savings", "nickname": "Demo run"}


@pytest.fixture
def approved():
    """The Artifact that actually ships — asked for by name, not opened by path."""
    return load_capability("member.open_sub_account")


def run(art, origin, tenant, overlay=None):
    urllib.request.urlopen(f"{origin}/reset", timeout=5).read()
    return replay(art, INPUTS, RunContext(origin=origin, tenant=tenant, overlay=overlay))


# ── B1: the unlabelled control ───────────────────────────────────────────────

def test_the_search_control_has_no_accessible_name(bank_app):
    surface = Surface(bank_app)
    try:
        surface.goto("/login")
        tb = surface.page.get_by_role("textbox")
        tb.nth(0).fill("svc_officer"); tb.nth(1).fill("officer-pw")
        surface.page.get_by_role("button", name="Sign in").click()
        surface.page.wait_for_load_state()
        assert surface.page.get_by_role("button", name="Search").count() == 0
    finally:
        surface.close()


def test_it_is_found_by_a_fallback_rung_and_the_log_says_which(approved, bank_app):
    r = run(approved, bank_app, "bank_a")
    assert r.status == "succeeded", r
    matched = {e["target"]: e["matched_by"] for e in r.trail if e.get("matched_by")}
    assert matched["t_member_number_button"] == "label_anchor"   # not role_name
    assert matched["t_sign_in"] == "role_name"                   # buttons with names still use it


# ── B2: one artifact, two institutions ───────────────────────────────────────

def test_the_artifact_fails_at_the_second_institution_without_an_overlay(approved, bank2_app):
    r = run(approved, bank2_app, "lakeside")
    assert r.status == "failed"


def test_the_same_artifact_succeeds_there_with_an_overlay(approved, bank2_app):
    overlay = overlay_for("lakeside")
    r = run(approved, bank2_app, "lakeside", overlay)
    assert r.status == "succeeded", r
    assert r.outputs["savings_balance"] == "$4210.00"
    assert r.outputs["new_account_number"].startswith("SA-")


def test_an_overlay_that_changes_behaviour_is_refused_before_the_browser_opens(approved, bank2_app):
    overlay = overlay_for("lakeside")
    overlay["transitions"] = [{"from_state": "s1_login", "to_state": "s2_search",
                               "action": {"type": "click", "target": "t_open"}}]
    r = run(approved, bank2_app, "lakeside", overlay)
    assert r.status == "refused"
    assert "overlay" in r.reason
