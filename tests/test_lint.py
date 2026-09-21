"""Lint rules a valid-looking Artifact must also pass before it can be approved.

These catch the bugs every prior attempt at this problem hit: a discovery literal
frozen into the recording, a placeholder nothing fills, an outcome promised to the
caller that nothing can produce.
"""

from cua.artifact import Artifact
from cua.lint import lint

from .fixtures import artifact_dict, overlay_dict


def codes(issues):
    return sorted(i.code for i in issues)


def test_a_clean_artifact_has_no_issues():
    assert lint(Artifact.model_validate(artifact_dict())) == []


def test_a_discovery_literal_in_a_step_is_rejected():
    d = artifact_dict()
    d["transitions"][1]["action"]["value"] = "54321"  # the member used during discovery
    assert "discovery_literal" in codes(lint(Artifact.model_validate(d)))


def test_a_discovery_literal_in_a_checkpoint_is_rejected():
    d = artifact_dict()
    d["states"][2]["checkpoint"] = {"type": "text_present", "value": "Member 54321"}
    assert "discovery_literal" in codes(lint(Artifact.model_validate(d)))


def test_a_discovery_literal_in_a_watcher_is_rejected():
    d = artifact_dict()
    d["watchers"][0]["trigger"] = {"type": "text_present", "value": "No records for 54321"}
    assert "discovery_literal" in codes(lint(Artifact.model_validate(d)))


def test_a_placeholder_with_no_matching_input_is_rejected():
    d = artifact_dict()
    d["transitions"][1]["action"]["value"] = "{{branch_code}}"
    assert "unknown_placeholder" in codes(lint(Artifact.model_validate(d)))


def test_a_watcher_naming_an_undeclared_outcome_is_rejected():
    d = artifact_dict()
    d["watchers"][0]["outcome"] = "ACCOUNT_FROZEN"
    assert "undeclared_outcome" in codes(lint(Artifact.model_validate(d)))


def test_a_declared_outcome_no_watcher_can_produce_is_rejected():
    d = artifact_dict()
    d["contract"]["outcomes"].append(
        {"code": "ACCOUNT_FROZEN", "meaning": "frozen", "resolver": "institution_staff"}
    )
    assert "unreachable_outcome" in codes(lint(Artifact.model_validate(d)))


def test_a_non_terminal_state_without_a_checkpoint_is_rejected():
    d = artifact_dict()
    d["states"][2]["checkpoint"] = None
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
    d["transitions"][0]["action"]["target"] = "t_missing"
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


# ── Tenant Overlays may change how things look, never how they behave ──────────

def test_a_clean_overlay_is_accepted():
    from cua.overlay import lint_overlay
    assert lint_overlay(Artifact.model_validate(artifact_dict()), overlay_dict()) == []


def test_an_overlay_cannot_add_a_step():
    from cua.overlay import lint_overlay
    o = overlay_dict()
    o["transitions"] = [{"from_state": "member_open", "to_state": "done", "action": {"type": "click", "target": "t_search"}}]
    issues = lint_overlay(Artifact.model_validate(artifact_dict()), o)
    assert "overlay_changes_behaviour" in sorted(i.code for i in issues)


def test_an_overlay_cannot_change_the_contract():
    from cua.overlay import lint_overlay
    o = overlay_dict()
    o["contract"] = {"outputs": {"savings_balance": {"type": "money"}}}
    issues = lint_overlay(Artifact.model_validate(artifact_dict()), o)
    assert "overlay_changes_behaviour" in sorted(i.code for i in issues)


def test_an_overlay_cannot_widen_needs():
    from cua.overlay import lint_overlay
    o = overlay_dict()
    o["needs"] = {"pages": ["/transfers/*"]}
    issues = lint_overlay(Artifact.model_validate(artifact_dict()), o)
    assert "overlay_widens_needs" in sorted(i.code for i in issues)
