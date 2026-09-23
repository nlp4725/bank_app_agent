"""Masking is by origin first, pattern second, and default-deny.

A name and a birthday have no shape a regex can find, so the mechanism that has to
work is knowing *which field* a value came from. See CONTEXT.md, "Redaction".
"""

import pytest
from pydantic import ValidationError

from cua.artifact import AppProfile, Artifact, Watcher, merged
from cua.profile import load_profile
from cua.redact import HIDDEN, PROTECTED, mask_value, redact_text

from .fixtures import artifact_dict


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


def test_the_artifact_still_returns_its_declared_outputs_in_full(bank_app):
    """Masking protects the record, never the answer."""
    from cua.engine import RunContext, replay
    art = merged(Artifact.model_validate(artifact_dict()),
                 load_profile("demo-core-servicing"))
    r = replay(art, {"member_number": "12345", "account_type": "savings",
                     "nickname": "Holiday fund"}, RunContext(origin=bank_app))
    assert r.outputs["savings_balance"] == "$4210.00"


# ── the two channels take opposite defaults, on purpose ──────────────────────

def test_values_are_allowlisted_but_pixels_are_deny_listed():
    profile = load_profile("demo-core-servicing")
    assert profile.readable_regions == ["t_balance", "t_new_number"]
    assert profile.sensitive_regions == ["t_member_name", "t_member_since"]
    # a control the model must use is readable in pixels though its value is hidden
    assert "t_ok" not in profile.sensitive_regions
    assert "t_ok" not in profile.readable_regions


def test_a_declared_sensitive_region_is_painted_black(bank_app):
    from cua.surface import Surface
    profile = load_profile("demo-core-servicing")
    masked = [profile.targets[n] for n in profile.sensitive_regions if n in profile.targets]
    surface = Surface(bank_app)
    try:
        surface.goto("/login")
        tb = surface.page.get_by_role("textbox")
        tb.nth(0).fill("svc_officer"); tb.nth(1).fill("officer-pw")
        surface.page.get_by_role("button", name="Sign in").click()
        surface.page.wait_for_load_state()
        surface.page.get_by_role("textbox").first.fill("12345")
        surface.page.get_by_role("button").last.click()
        surface.page.wait_for_load_state(); surface.page.wait_for_timeout(800)
        surface.screenshot("/tmp/_plain.png", mask_targets=[])
        surface.screenshot("/tmp/_masked.png", mask_targets=masked)
        assert open("/tmp/_plain.png", "rb").read() != open("/tmp/_masked.png", "rb").read()
    finally:
        surface.close()


# ── the chokepoint is one module, and replay goes through it too ─────────────

def test_the_redactor_masks_pixels_on_the_replay_path_not_only_in_discovery():
    """The gap this closed: EvidenceWriter.snap used to capture unmasked, so a
    failure screenshot and an Operator's intervention bypassed layer 4."""
    from cua.evidence import EvidenceWriter
    from cua.redact import for_app

    redactor = for_app("demo-core-servicing")
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
    writer = EvidenceWriter(tmp(), None, redactor=redactor)
    writer.snap(surface)
    writer.close()
    assert surface.asked and len(surface.asked) == 2, \
        "a replay screenshot was captured without the declared Sensitive Regions"
    assert surface.readable == {"Savings balance", "New account number"}, \
        "value cells must be painted unless their caption is a Readable Anchor"
    assert "Member [0-9]{5}" in surface.patterns


def test_a_writer_with_no_profile_still_masks_text_and_patterns():
    from cua.evidence import EvidenceWriter
    writer = EvidenceWriter(tmp(), None)
    record = writer.event("run_x", "observed", note="card 4111 1111 1111 1111")
    writer.close()
    assert "[card]" in record["note"]


def tmp():
    import tempfile
    from pathlib import Path
    return Path(tempfile.mkdtemp())


# ── pixels take the same default as text ─────────────────────────────────────

def _member_page(surface):
    surface.goto("/login")
    tb = surface.page.get_by_role("textbox")
    tb.nth(0).fill("svc_officer"); tb.nth(1).fill("officer-pw")
    surface.page.get_by_role("button", name="Sign in").click()
    surface.page.wait_for_load_state()
    surface.page.get_by_role("textbox").first.fill("12345")
    surface.page.get_by_role("button").last.click()
    surface.page.wait_for_load_state(); surface.page.wait_for_timeout(800)


def _is_black(png, box):
    from PIL import Image
    img = Image.open(png).convert("RGB")
    x, y = int(box["x"] + box["width"] / 2), int(box["y"] + box["height"] / 2)
    return img.getpixel((x, y)) == (0, 0, 0)


def test_a_value_cell_not_declared_readable_is_painted_black(bank_app, tmp_path):
    """The Checking balance is a value nobody declared readable: hidden in text, so hidden
    in pixels. The Savings balance is a Readable Anchor: visible in both. The member
    number in the heading is not a cell at all; the profile names it by pattern."""
    from cua.redact import Redactor
    from cua.surface import Surface
    surface = Surface(bank_app)
    try:
        _member_page(surface)
        cells = {c["anchor"]: c["box"] for c in surface.values(0)}
        heading = surface.page.get_by_text("Member 12345").first.bounding_box()
        shot = str(tmp_path / "member.png")
        Redactor(load_profile("demo-core-servicing")).screenshot(surface, shot)
        assert _is_black(shot, cells["Checking balance"])
        assert not _is_black(shot, cells["Savings balance"])
        assert _is_black(shot, heading)
    finally:
        surface.close()


def test_a_crop_is_only_ever_of_a_control_never_of_a_value():
    """Discovery crops a target before acting, and only for a click: a field after
    typing or a cell being read is a picture of a value."""
    import inspect
    from cua import discovery
    src = inspect.getsource(discovery.discover)
    assert 'if call.name == "click" else None' in src
    assert src.index("surface.crop(") < src.index("record = _perform(")
