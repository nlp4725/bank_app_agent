"""Tenant Overlays may change how things look, never how they behave. A key nothing applies is refused rather than ignored."""

from cua.domain.artifact import Artifact
from cua.governance.overlay import lint_overlay
from tests.support.artifact import artifact_dict, overlay_dict

# ── Tenant Overlays may change how things look, never how they behave ──────────

def test_a_clean_overlay_is_accepted():
    assert lint_overlay(Artifact.model_validate(artifact_dict()), overlay_dict()) == []


def test_an_overlay_cannot_add_a_step():
    o = overlay_dict()
    o["transitions"] = [{"from_state": "member_open", "to_state": "done", "action": {"type": "click", "target": "t_search"}}]
    issues = lint_overlay(Artifact.model_validate(artifact_dict()), o)
    assert "overlay_changes_behaviour" in sorted(i.code for i in issues)


def test_an_overlay_cannot_change_the_contract():
    o = overlay_dict()
    o["contract"] = {"outputs": {"savings_balance": {"type": "money"}}}
    issues = lint_overlay(Artifact.model_validate(artifact_dict()), o)
    assert "overlay_changes_behaviour" in sorted(i.code for i in issues)


def test_an_overlay_cannot_widen_needs():
    o = overlay_dict()
    o["needs"] = {"pages": ["/transfers/*"]}
    issues = lint_overlay(Artifact.model_validate(artifact_dict()), o)
    assert "overlay_widens_needs" in sorted(i.code for i in issues)


def test_an_overlay_key_that_nothing_applies_is_refused_not_ignored():
    """`timeouts` and `watcher_triggers` used to lint clean and then do nothing, so a
    reviewer could approve a patch with no effect."""
    art = Artifact.model_validate(artifact_dict())
    for key, value in (("timeouts", {"t_balance": 8000}),
                       ("watcher_triggers", {"w_system_notice": {"type": "text_present",
                                                                 "value": "Notice"}})):
        issues = lint_overlay(art, dict(overlay_dict(), **{key: value}))
        assert any(i.code == "overlay_unknown_key" and i.where == key for i in issues), \
            f"an overlay declaring {key!r} was accepted although nothing applies it"
