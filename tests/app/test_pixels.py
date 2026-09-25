"""Pixels take the same default-deny as text, against the running app.

A declared Sensitive Region is painted black at capture; a value cell nobody declared
readable is painted too; the page text a model reads hides what no pattern could find;
and the answer still reaches the caller in full. The pure masking rules are in
tests/unit/test_redaction.py.
"""

from cua.domain.artifact import Artifact, merged
from cua.governance.profile import load_profile
from tests.support.artifact import artifact_dict
from tests.support.doubles import attended


def test_the_artifact_still_returns_its_declared_outputs_in_full(bank_app):
    """Masking protects the record, never the answer."""
    from cua.replay.engine import RunContext, replay
    art = merged(Artifact.model_validate(artifact_dict()),
                 load_profile("demo-core-servicing"))
    r = replay(art, {"member_number": "12345", "account_type": "savings",
                     "nickname": "Holiday fund"}, RunContext(origin=bank_app, **attended()))
    assert r.outputs["savings_balance"] == "$4210.00"
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
    from cua.evidence import Redactor
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
def test_the_page_text_the_model_reads_hides_a_value_no_pattern_can_find(bank_app):
    """The gap this closed: the 'visible text' block went through the pattern net only,
    so a name — which no pattern can find — reached the model and, repeated in its
    reason, the trail. Page text now goes through origin masking like the cells do."""
    from cua.evidence import Redactor
    from cua.surface import Surface
    surface = Surface(bank_app)
    try:
        _member_page(surface)
        raw = surface.text()
        assert "Jane Q. Public" in raw                      # it is on the page
        shown = Redactor(load_profile("demo-core-servicing")).page_text(surface)
        assert "Jane Q. Public" not in shown
        assert "Member 12345" not in shown                  # declared text pattern
        assert "(hidden)" in shown
        assert "Savings balance" in shown                   # captions stay: the model needs them
    finally:
        surface.close()
