"""Lint rules a valid-looking Artifact must also pass before it can be approved.

These catch the bugs every prior attempt at this problem hit: a discovery literal
frozen into the recording, a placeholder nothing fills, an outcome promised to the
caller that nothing can produce.
"""

from cua.authoring.lint import lint
from cua.domain.artifact import Artifact
from tests.support.artifact import artifact_dict


def transition_to(d, target):
    """The transition whose action acts on `target` — tests should not depend on order."""
    return next(t for t in d["transitions"] if t["action"].get("target") == target)


def state(d, state_id):
    return next(s for s in d["states"] if s["id"] == state_id)


def codes(issues):
    return sorted(i.code for i in issues)


def test_a_clean_artifact_has_no_issues():
    assert lint(Artifact.model_validate(artifact_dict())) == []


def test_a_discovery_literal_in_a_step_is_rejected():
    d = artifact_dict()
    transition_to(d, "t_member_field")["action"]["value"] = "54321"  # the discovery member
    assert "discovery_literal" in codes(lint(Artifact.model_validate(d)))


def test_a_discovery_literal_in_a_checkpoint_is_rejected():
    d = artifact_dict()
    state(d, "member_open")["checkpoint"] = {"type": "text_present", "value": "Member 54321"}
    assert "discovery_literal" in codes(lint(Artifact.model_validate(d)))


def test_a_discovery_literal_in_a_watcher_is_rejected():
    d = artifact_dict()
    d["watchers"][0]["trigger"] = {"type": "text_present", "value": "No records for 54321"}
    assert "discovery_literal" in codes(lint(Artifact.model_validate(d)))


def test_a_placeholder_with_no_matching_input_is_rejected():
    d = artifact_dict()
    transition_to(d, "t_member_field")["action"]["value"] = "{{branch_code}}"
    assert "unknown_placeholder" in codes(lint(Artifact.model_validate(d)))


def test_a_watcher_naming_an_undeclared_outcome_is_rejected():
    d = artifact_dict()
    d["watchers"][0]["outcome"] = "ACCOUNT_FROZEN"
    assert "undeclared_outcome" in codes(lint(Artifact.model_validate(d)))


def test_the_held_out_condition_is_absent_on_purpose():
    """MAX_ACCOUNTS_REACHED is deliberately not in the artifact: member 33333 must
    produce an Unknown State until a Reviewer adds the Watcher (see docs/evaluation.md)."""
    d = artifact_dict()
    assert "MAX_ACCOUNTS_REACHED" not in [o["code"] for o in d["contract"]["outcomes"]]
    assert lint(Artifact.model_validate(d)) == []


def test_a_declared_outcome_no_watcher_can_produce_is_rejected():
    d = artifact_dict()
    d["contract"]["outcomes"].append(
        {"code": "ACCOUNT_FROZEN", "meaning": "frozen", "resolver": "institution_staff"}
    )
    assert "unreachable_outcome" in codes(lint(Artifact.model_validate(d)))


def test_a_non_terminal_state_without_a_checkpoint_is_rejected():
    d = artifact_dict()
    state(d, "member_open")["checkpoint"] = None
    assert "missing_checkpoint" in codes(lint(Artifact.model_validate(d)))


def test_a_secret_used_but_not_declared_in_needs_is_rejected():
    d = artifact_dict()
    d["needs"]["secrets"] = ["login_username"]
    assert "undeclared_secret" in codes(lint(Artifact.model_validate(d)))


def test_a_transition_between_states_that_do_not_exist_is_rejected():
    d = artifact_dict()
    d["transitions"][-1]["to_state"] = "nowhere"
    assert "unknown_state" in codes(lint(Artifact.model_validate(d)))


def test_a_target_referenced_but_not_defined_is_rejected():
    d = artifact_dict()
    transition_to(d, "t_signin")["action"]["target"] = "t_missing"
    assert "unknown_target" in codes(lint(Artifact.model_validate(d)))


def test_a_consequential_step_without_a_verification_check_cannot_run_unattended():
    d = artifact_dict()
    for t in d["transitions"]:
        if t["risk"] == "consequential":
            del t["verify_effect"]
    issues = lint(Artifact.model_validate(d), unattended=True)
    assert "consequential_without_verification" in codes(issues)
    # the same Artifact is fine when an Operator is on hand
    assert "consequential_without_verification" not in codes(lint(Artifact.model_validate(d)))


def test_needs_outside_the_declared_role_are_rejected():
    d = artifact_dict()
    d["needs"]["pages"].append("/admin/*")
    assert "needs_exceed_role" in codes(lint(Artifact.model_validate(d)))


def test_an_unapproved_artifact_is_flagged_for_unattended_use():
    d = artifact_dict()
    d["capability"]["status"] = "draft"
    assert "not_approved" in codes(lint(Artifact.model_validate(d), unattended=True))


def test_a_consequential_artifact_needs_two_approvals():
    d = artifact_dict()
    d["capability"]["approvals"] = ["reviewer:nasi"]
    assert "needs_two_person_approval" in codes(lint(Artifact.model_validate(d)))


def test_a_text_trigger_too_short_to_name_a_screen_is_refused():
    """The letter y matches nearly every page; a business outcome on it is a coin flip."""
    d = artifact_dict()
    d["watchers"].append({"id": "w_y", "trigger": {"type": "text_present", "value": "y"},
                          "condition": "business_outcome", "outcome": "MEMBER_NOT_FOUND",
                          "provenance": "reviewer:test"})
    codes = [i.code for i in lint(Artifact.model_validate(d))]
    assert "weak_trigger" in codes


def test_two_states_with_one_id_are_refused():
    d = artifact_dict()
    d["states"].append(dict(d["states"][0]))          # a second "sign_in"
    codes = [i.code for i in lint(Artifact.model_validate(d))]
    assert "duplicate_state" in codes
