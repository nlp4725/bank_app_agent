"""Masking is by origin first, pattern second, and default-deny — without a browser.

The four tests that paint a screenshot or read a live page are in
tests/app/test_pixels.py.

A name and a birthday have no shape a regex can find, so the mechanism that has to
work is knowing *which field* a value came from. See CONTEXT.md, "Redaction".
"""

import pytest
from pydantic import ValidationError

from cua.domain.artifact import Watcher
from cua.evidence import HIDDEN, PROTECTED, mask_value, redact_text
from cua.governance.profile import load_profile

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


# ── the chokepoint is one module, and replay goes through it too ─────────────

def test_the_redactor_masks_pixels_on_the_replay_path_not_only_in_discovery():
    """The gap this closed: EvidenceWriter.snap used to capture unmasked, so a
    failure screenshot and an Operator's intervention bypassed layer 4."""
    from cua.evidence import EvidenceWriter
    from cua.governance.profile import redactor_for

    redactor = redactor_for("demo-core-servicing")
    assert len(redactor.masked_targets()) == 2

    class Recorder:
        """Stands in for the browser: records what it was asked to mask."""
        def __init__(self): self.asked = None; self.readable = None; self.patterns = None
        def screenshot(self, path, mask_targets=None, scale="css", readable_anchors=None,
                       sensitive_text=()):
            self.asked, self.readable, self.patterns = mask_targets, readable_anchors, sensitive_text
            pathlib_write(path)

    def pathlib_write(path):
        from pathlib import Path
        Path(path).write_bytes(b"png")

    surface = Recorder()
    writer = EvidenceWriter(tmp(), redactor=redactor)
    writer.snap(surface)
    writer.close()
    assert surface.asked and len(surface.asked) == 2, \
        "a replay screenshot was captured without the declared Sensitive Regions"
    assert surface.readable == {"Savings balance", "New account number"}, \
        "value cells must be painted unless their caption is a Readable Anchor"
    assert "Member [0-9]{5}" in surface.patterns


def test_an_intervention_request_leaves_through_the_redactor(tmp_path):
    """The gap this closed: Intervention.write dumped its own __dict__ into the
    evidence directory, so the one file an Operator reads never met the Redactor."""
    import json

    from cua.evidence import EvidenceWriter
    from cua.replay.handoff import Intervention
    writer = EvidenceWriter(tmp_path / "run_x")
    request = Intervention(run_id="run_x", capability="c", state="s", watcher=None,
                           reason="contact jane@example.com about card 4111 1111 1111 1111",
                           url="http://127.0.0.1:5001/members/12345", screenshot="")
    path = writer.intervention(request)
    writer.close()
    body = json.loads(path.read_text())
    assert "[email]" in body["reason"] and "[card]" in body["reason"]
    assert body["url"] == request.url            # what the Operator needs, still there


def test_a_writer_with_no_profile_still_masks_text_and_patterns():
    from cua.evidence import EvidenceWriter
    writer = EvidenceWriter(tmp())
    record = writer.event("run_x", "observed", note="card 4111 1111 1111 1111")
    writer.close()
    assert "[card]" in record["note"]


def tmp():
    import tempfile
    from pathlib import Path
    return Path(tempfile.mkdtemp())


def test_a_crop_is_only_ever_of_a_control_never_of_a_value():
    """Discovery crops a target before acting, and only for a click: a field after
    typing or a cell being read is a picture of a value."""
    import inspect

    from cua import discovery
    src = inspect.getsource(discovery.discover)
    assert 'if call.name == "click" else None' in src
    assert src.index("surface.crop(") < src.index("record = _perform(")
