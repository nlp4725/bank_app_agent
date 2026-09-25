"""The Predicate vocabulary, tested without a browser.

The point of the module is that evaluating a Checkpoint needs only three things from
a screen — its text, its address, and whether a Target resolves. A scripted stand-in
supplies those, so the closed vocabulary has tests that run in milliseconds and do
not depend on the demo app being up.
"""

import pytest

from cua.domain.artifact import Artifact
from cua.domain.placeholders import render
from cua.replay.predicates import Predicates
from tests.support.artifact import artifact_dict
from tests.support.doubles import ScriptedSurface


@pytest.fixture
def artifact():
    return Artifact.model_validate(artifact_dict())


def evaluate(artifact, predicate, surface, **inputs):
    return Predicates(surface, artifact, inputs).holds(predicate, timeout_ms=0)


def P(**kw):
    from cua.domain.artifact import Artifact as _A
    return _A.model_validate({**artifact_dict(), "states": [
        {"id": "s", "checkpoint": kw}]}).states[0].checkpoint


# ── rendering ────────────────────────────────────────────────────────────────

def test_a_placeholder_is_filled_from_the_inputs():
    assert render("member {{member_number}}", {"member_number": "12345"}) == "member 12345"


def test_an_unknown_placeholder_is_left_as_written():
    assert render("{{nope}}", {}) == "{{nope}}"


def test_every_string_field_is_rendered_not_a_hardcoded_list(artifact):
    """The bug this shape prevents: a Predicate field added later silently stopped
    having its placeholders filled, because the renderer named fields by hand."""
    surface = ScriptedSurface(text="member 12345 found")
    assert evaluate(artifact, P(type="text_present", value="member {{member_number}}"),
                    surface, member_number="12345")


def test_rendering_reaches_inside_all_and_any(artifact):
    surface = ScriptedSurface(text="member 12345 found", url="http://app/members/12345")
    both = P(type="all", of=[{"type": "text_present", "value": "{{member_number}}"},
                             {"type": "url_matches", "pattern": "/members/{{member_number}}"}])
    assert evaluate(artifact, both, surface, member_number="12345")
    assert not evaluate(artifact, both, surface, member_number="99999")


# ── the four shapes ──────────────────────────────────────────────────────────

def test_text_present(artifact):
    assert evaluate(artifact, P(type="text_present", value="No records"),
                    ScriptedSurface(text="No records found"))
    assert not evaluate(artifact, P(type="text_present", value="No records"),
                        ScriptedSurface(text="Member detail"))


def test_url_matches_is_a_contains_match(artifact):
    p = P(type="url_matches", pattern="/members/")
    assert evaluate(artifact, p, ScriptedSurface(url="http://app/members/12345"))
    assert not evaluate(artifact, p, ScriptedSurface(url="http://app/search"))


def test_element_present_asks_the_surface_to_resolve_the_target(artifact):
    p = P(type="element_present", target="t_signin")
    assert evaluate(artifact, p, ScriptedSurface(present=["t_signin"], targets=artifact.targets))
    assert not evaluate(artifact, p, ScriptedSurface(present=[], targets=artifact.targets))


def test_an_element_predicate_naming_no_target_is_false_not_an_error(artifact):
    assert not evaluate(artifact, P(type="element_present", target="t_nothing"),
                        ScriptedSurface(present=["t_signin"], targets=artifact.targets))


def test_field_value_compares_and_can_ask_only_for_non_empty(artifact):
    surface = ScriptedSurface(present=["t_member_field"], targets=artifact.targets,
                              values={"t_member_field": "12345"})
    assert evaluate(artifact, P(type="field_value", target="t_member_field",
                                equals="{{member_number}}"), surface, member_number="12345")
    assert not evaluate(artifact, P(type="field_value", target="t_member_field",
                                    equals="{{member_number}}"), surface, member_number="99999")
    assert evaluate(artifact, P(type="field_value", target="t_member_field", non_empty=True),
                    surface)


def test_any_needs_one_and_all_needs_every(artifact):
    surface = ScriptedSurface(text="Open Accounts")
    hit = {"type": "text_present", "value": "Open Accounts"}
    miss = {"type": "text_present", "value": "System notice"}
    assert evaluate(artifact, P(type="any", of=[miss, hit]), surface)
    assert not evaluate(artifact, P(type="all", of=[miss, hit]), surface)


# ── polling and the Verification Check ───────────────────────────────────────

def test_a_predicate_that_never_holds_polls_until_the_deadline(artifact):
    surface = ScriptedSurface(text="")
    got = Predicates(surface, artifact, {}).holds(
        P(type="text_present", value="never"), timeout_ms=60)
    assert got is False and surface.waits > 0


def test_the_verification_check_looks_somewhere_else_before_asking(artifact):
    surface = ScriptedSurface(text="SA-2001 opened")
    ok = Predicates(surface, artifact, {"member_number": "12345"}).after_going_to(
        "/members/{{member_number}}", P(type="text_present", value="SA-"), timeout_ms=0)
    assert ok
    assert surface.went_to == ["/members/12345"]


# ── narration is behind its own seam ─────────────────────────────────────────

def test_a_run_says_nothing_unless_somebody_is_watching():
    """Presentation used to be three knobs on RunContext and a print() in the loop."""
    from cua.replay.engine import RunContext
    from cua.replay.narration import Console, Silent, from_env

    assert RunContext(origin="http://app").narrator is None      # Silent by default
    assert Silent().slow_mo_ms == 0
    for field in ("verbose", "slow_mo_ms", "hold_open_s"):
        assert not hasattr(RunContext(origin="http://app"), field), \
            f"{field} is presentation, not run configuration"

    assert isinstance(from_env({}), Silent)
    watched = from_env({"HEADED": "1"})
    assert isinstance(watched, Console) and watched.slow_mo_ms == 900
