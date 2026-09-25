"""The schema is a whitelist: an Artifact can only name things the engine implements."""

import pytest
from pydantic import ValidationError

from cua.domain.artifact import Artifact
from tests.support.artifact import artifact_dict


def test_a_well_formed_artifact_parses():
    art = Artifact.model_validate(artifact_dict())
    assert art.capability.id == "member.open_sub_account"
    assert art.contract.inputs["member_number"].pattern == r"^[0-9]{5}$"


def test_a_predicate_outside_the_vocabulary_is_rejected():
    d = artifact_dict()
    d["states"][0]["checkpoint"] = {"type": "looks_about_right", "value": "x"}
    with pytest.raises(ValidationError):
        Artifact.model_validate(d)


def test_a_target_rung_outside_the_vocabulary_is_rejected():
    d = artifact_dict()
    d["targets"]["t_search"] = {"rungs": [{"kind": "dom_css", "value": "button.iconbtn"}]}
    with pytest.raises(ValidationError):
        Artifact.model_validate(d)


def test_risk_must_be_safe_or_consequential():
    d = artifact_dict()
    d["transitions"][0]["risk"] = "medium"
    with pytest.raises(ValidationError):
        Artifact.model_validate(d)


def test_a_type_action_cannot_carry_both_a_value_and_a_secret_reference():
    d = artifact_dict()
    d["transitions"][0]["action"] = {
        "type": "type",
        "target": "t_member_field",
        "value": "{{member_number}}",
        "value_ref": "login_password",
    }
    with pytest.raises(ValidationError):
        Artifact.model_validate(d)


def test_a_type_action_must_carry_one_of_them():
    d = artifact_dict()
    d["transitions"][0]["action"] = {"type": "type", "target": "t_member_field"}
    with pytest.raises(ValidationError):
        Artifact.model_validate(d)


def test_an_outcome_must_declare_who_can_resolve_it():
    d = artifact_dict()
    del d["contract"]["outcomes"][0]["resolver"]
    with pytest.raises(ValidationError):
        Artifact.model_validate(d)


def test_a_business_outcome_may_never_be_marked_retryable():
    d = artifact_dict()
    d["contract"]["outcomes"][0]["retry_same_inputs"] = "always"
    with pytest.raises(ValidationError):
        Artifact.model_validate(d)


# ── the vocabulary is exactly four actions and four predicates ────────────────

@pytest.mark.parametrize("action", [
    {"type": "wait", "ms": 1000},          # waiting is a property of a transition
    {"type": "scroll", "target": "t_open"},  # the driver scrolls into view itself
    {"type": "download", "target": "t_open"},
])
def test_actions_outside_the_vocabulary_are_rejected(action):
    d = artifact_dict()
    d["transitions"][0]["action"] = action
    with pytest.raises(ValidationError):
        Artifact.model_validate(d)


@pytest.mark.parametrize("predicate", [
    {"type": "count", "target": "t_open", "equals": 3},
    {"type": "element_absent", "target": "t_open"},
])
def test_predicates_outside_the_vocabulary_are_rejected(predicate):
    d = artifact_dict()
    d["states"][0]["checkpoint"] = predicate
    with pytest.raises(ValidationError):
        Artifact.model_validate(d)


def test_a_transition_cannot_carry_a_precondition():
    """The source state's Checkpoint already asserts where we must be."""
    d = artifact_dict()
    d["transitions"][0]["precondition"] = {"type": "text_present", "value": "Sign in"}
    with pytest.raises(ValidationError):
        Artifact.model_validate(d)


def test_a_target_may_declare_the_frame_it_lives_in():
    art = Artifact.model_validate(artifact_dict())
    assert art.targets["t_balance"].frame.url_contains == "/panel"
    assert art.targets["t_open"].frame is None      # absent means the main document


def test_a_target_ladder_is_ordered_strongest_first():
    art = Artifact.model_validate(artifact_dict())
    assert [r.kind for r in art.targets["t_search"].rungs] == ["role_name", "label_anchor", "picture"]


# ── App Profile: what every capability on one vendor app shares ───────────────

def test_app_wide_watchers_reach_every_artifact():
    from cua.domain.artifact import merged
    art = Artifact.model_validate(artifact_dict())
    profile = load_profile("demo-core-servicing")
    assert [w.id for w in art.watchers] == ["w_not_found", "w_not_authorized", "w_validation"]
    full = merged(art, profile)
    assert "w_session_expired" in [w.id for w in full.watchers]
    assert "t_ok" in full.targets              # the profile's targets come too
    assert lint(full) == []


def test_an_artifacts_own_watcher_wins_over_the_profiles():
    from cua.domain.artifact import merged
    d = artifact_dict()
    d["watchers"].append({
        "id": "w_system_notice",
        "trigger": {"type": "text_present", "value": "System notice for this capability"},
        "condition": "hard_failure", "provenance": "reviewer:nasi"})
    full = merged(Artifact.model_validate(d), load_profile("demo-core-servicing"))
    notice = [w for w in full.watchers if w.id == "w_system_notice"]
    assert len(notice) == 1
    assert notice[0].condition == "hard_failure"      # the artifact's, not the profile's


def test_a_profile_for_another_app_is_refused():
    import pytest

    from cua.domain.artifact import AppProfile, merged
    p = load_profile("demo-core-servicing").model_dump(mode="python")
    p["app_profile"] = "some-other-product"
    with pytest.raises(ValueError):
        merged(Artifact.model_validate(artifact_dict()), AppProfile.model_validate(p))
