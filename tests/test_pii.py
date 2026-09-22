"""Masking is by origin first, pattern second, and default-deny.

A name and a birthday have no shape a regex can find, so the mechanism that has to
work is knowing *which field* a value came from. See CONTEXT.md, "Redaction".
"""

import pytest
from pydantic import ValidationError

from cua.artifact import AppProfile, Artifact, Watcher, merged
from cua.redact import HIDDEN, PROTECTED, mask_value, redact_text

from .fixtures import app_profile_dict, artifact_dict


# ── by origin: what patterns cannot catch ────────────────────────────────────

def test_a_name_is_hidden_although_no_pattern_could_find_it():
    readable = {"t_balance"}
    assert mask_value("t_member_name", "Jane Q. Public", readable) == HIDDEN


def test_a_birthday_is_hidden_by_origin_too():
    assert mask_value("t_dob", "1981-04-02", set()) == HIDDEN


def test_a_declared_readable_value_comes_through():
    assert mask_value("t_balance", "4210.00", {"t_balance"}) == "4210.00"


def test_a_readable_value_still_passes_the_pattern_net():
    assert mask_value("t_notes", "call 415-555-0134", {"t_notes"}) == "call [phone]"


def test_a_password_is_never_read_even_if_declared_readable():
    assert mask_value("t_password", "officer-pw", {"t_password"}, is_password=True) == PROTECTED


def test_an_undeclared_field_is_hidden_by_default():
    """Default-deny: a new screen is safe until someone declares otherwise."""
    assert mask_value("t_anything_new", "whatever it holds", set()) == HIDDEN


# ── the pattern net, for values that do flow through ─────────────────────────

@pytest.mark.parametrize("raw,expected", [
    ("SSN 123-45-6789", "SSN [ssn]"),
    ("card 4111 1111 1111 1111", "card [card]"),
    ("a@b.com", "[email]"),
    ("$4,210.00", "$*,***.**"),
    ("opened 2014-03-02", "opened [date]"),
    ("(415) 555-0134", "[phone]"),
])
def test_patterns_catch_shaped_values(raw, expected):
    assert redact_text(raw) == expected


# ── extraction is an allowlist: declared capture groups, never page text ─────

def test_a_watcher_may_extract_a_declared_capture_group():
    w = Watcher.model_validate({
        "id": "w_max", "trigger": {"type": "text_present", "value": "Maximum"},
        "condition": "business_outcome", "outcome": "X", "provenance": "reviewer:nasi",
        "extract": {"limit": {"from": "regex", "pattern": r"maximum of (\d+)"}},
    })
    assert w.extract["limit"].pattern == r"maximum of (\d+)"


def test_a_watcher_may_not_extract_free_page_text():
    with pytest.raises(ValidationError):
        Watcher.model_validate({
            "id": "w_bad", "trigger": {"type": "text_present", "value": "Error"},
            "condition": "business_outcome", "outcome": "X", "provenance": "reviewer:nasi",
            "extract": {"message": {"from": "text_of", "target": "t_banner"}},
        })


def test_an_extract_pattern_without_a_capture_group_is_rejected():
    with pytest.raises(ValidationError):
        Watcher.model_validate({
            "id": "w_bad", "trigger": {"type": "text_present", "value": "Error"},
            "condition": "business_outcome", "outcome": "X", "provenance": "reviewer:nasi",
            "extract": {"limit": {"from": "regex", "pattern": r"maximum of \d+"}},
        })


# ── declared regions live in the App Profile, reviewable as data ─────────────

def test_readable_regions_are_declared_on_the_app_profile():
    profile = AppProfile.model_validate(app_profile_dict())
    assert "t_balance" in profile.readable_regions
    assert "t_member_name" not in profile.readable_regions


def test_the_artifact_still_returns_its_declared_outputs_in_full(bank_app):
    """Masking protects the record, never the answer."""
    from cua.engine import RunContext, replay
    art = merged(Artifact.model_validate(artifact_dict()),
                 AppProfile.model_validate(app_profile_dict()))
    r = replay(art, {"member_number": "12345", "account_type": "savings",
                     "nickname": "Holiday fund"}, RunContext(origin=bank_app))
    assert r.outputs["savings_balance"] == "$4210.00"
