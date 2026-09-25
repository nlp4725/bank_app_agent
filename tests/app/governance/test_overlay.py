"""B2, live: one artifact recorded at one institution runs at another with a small Overlay, and an Overlay that would change behaviour is refused before the browser opens."""

import urllib.request

import pytest

from cua.governance.store import load_capability, overlay_for
from cua.replay.engine import RunContext, replay
from tests.support.doubles import attended

INPUTS = {"member_number": "12345", "account_type": "savings", "nickname": "Demo run"}


@pytest.fixture
def approved():
    """The Artifact that actually ships — asked for by name, not opened by path."""
    return load_capability("member.open_sub_account")


def run(art, origin, tenant, overlay=None):
    urllib.request.urlopen(f"{origin}/reset", timeout=5).read()
    return replay(art, INPUTS, RunContext(origin=origin, tenant=tenant, overlay=overlay,
                                          **attended()))


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
