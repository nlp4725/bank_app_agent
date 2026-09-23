"""Start with a goal: the proposal is validated, the conversation is scripted.

No model and no browser: `propose` and `discover` are handed in, so what is tested is
the shape the model must return and what the Reviewer is asked.
"""

import pytest

from cua.discovery import ProposalError, spec_from_proposal
from tools import start

VENDOR = "demo-core-servicing"

PROPOSAL = {
    "capability_id": "member.read_savings_balance",
    "role": "balance_reader",
    "why_this_role": "The goal only reads a value.",
    "goal": "Look up member {member_number} and read their savings balance",
    "inputs": [{"name": "member_number", "type": "string", "pattern": "^[0-9]{5}$",
                "values": None, "max_length": None, "sensitive": True, "example": "54321"}],
    "outputs": [{"name": "savings_balance", "type": "money", "sensitive": False}],
    "outcomes": [{"code": "MEMBER_NOT_FOUND", "meaning": "No such member.",
                  "resolver": "member", "caller_hint": "Re-check the number."}],
}


def test_a_proposal_becomes_a_discovery_request_in_the_engine_s_contract_shape():
    spec = spec_from_proposal(PROPOSAL, VENDOR)
    assert spec["role"] == "balance_reader"
    assert spec["contract"]["inputs"]["member_number"] == {
        "type": "string", "sensitive": True, "pattern": "^[0-9]{5}$"}
    assert spec["contract"]["outputs"] == {"savings_balance": {"type": "money", "sensitive": False}}
    assert spec["contract"]["outcomes"][0]["caller_hint"] == "Re-check the number."
    assert spec["example_values"] == {"member_number": "54321"}


def test_a_role_the_app_does_not_define_is_refused():
    with pytest.raises(ProposalError, match="not a Role"):
        spec_from_proposal(dict(PROPOSAL, role="superuser"), VENDOR)


def test_a_resolver_the_schema_does_not_know_is_refused():
    bad = dict(PROPOSAL, outcomes=[dict(PROPOSAL["outcomes"][0], resolver="the_model")])
    with pytest.raises(ProposalError, match="not a valid Contract"):
        spec_from_proposal(bad, VENDOR)


def test_a_capability_that_returns_nothing_is_refused():
    with pytest.raises(ProposalError, match="returns something"):
        spec_from_proposal(dict(PROPOSAL, outputs=[], outcomes=[]), VENDOR)


def _scripted(answers):
    answers = iter(answers)
    return lambda prompt: next(answers)


def test_the_conversation_asks_goal_then_values_then_confirms_and_runs(tmp_path, monkeypatch):
    monkeypatch.setattr(start, "CONTRACTS", tmp_path)
    seen = {}

    def fake_discover(request):
        seen["request"] = request
        class R:
            ending, outputs, trace_dir, draft, suggestions, actions = (
                "goal_reached", {"savings_balance": "$1.00"}, str(tmp_path), None, [], [])
            def __str__(self): return "ok"
        return R()

    code = start.run(ask=_scripted(["read the savings balance of a member", "y", "12345", "n"]),
                     propose=lambda goal, app, **kw: spec_from_proposal(PROPOSAL, app),
                     discover_fn=fake_discover)
    assert code == 0
    r = seen["request"]
    assert r.goal == "Look up member 12345 and read their savings balance"
    assert r.role == "balance_reader" and r.capability_id == "member.read_savings_balance"
    assert r.example_values == {"member_number": "12345"}
    assert r.headless is True                       # answered "n" to watching
    assert (tmp_path / "read_savings_balance.yaml").exists()


def test_a_value_that_breaks_the_contract_is_asked_again(tmp_path, monkeypatch):
    monkeypatch.setattr(start, "CONTRACTS", tmp_path)
    asked = []
    def ask(prompt):
        asked.append(prompt)
        return {1: "y", 2: "abc", 3: "12345"}.get(len(asked), "n")
    ran = {}
    class R:
        ending, outputs, trace_dir, draft, suggestions, actions = "goal_reached", {}, "", None, [], []
        def __str__(self): return "ok"
    def fake_discover(r):
        ran["values"] = r.example_values
        return R()
    start.run(goal="read a balance", ask=ask,
              propose=lambda goal, app, **kw: spec_from_proposal(PROPOSAL, app),
              discover_fn=fake_discover)
    assert asked[1].startswith("member_number") and asked[2].startswith("member_number")
    assert ran["values"] == {"member_number": "12345"}      # the bad value never got through


def test_edit_saves_the_proposal_and_runs_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(start, "CONTRACTS", tmp_path)
    code = start.run(goal="read a balance", ask=_scripted(["e"]),
                     propose=lambda goal, app, **kw: spec_from_proposal(PROPOSAL, app),
                     discover_fn=lambda r: pytest.fail("must not run"))
    assert code == 0
    saved = (tmp_path / "read_savings_balance.yaml").read_text()
    assert "member.read_savings_balance" in saved and "balance_reader" in saved


def test_a_failed_proposal_ends_the_conversation_cleanly():
    def bad(goal, app, **kw):
        raise ProposalError("nope")
    assert start.run(goal="x", ask=_scripted([]), propose=bad,
                     discover_fn=lambda r: pytest.fail("must not run")) == 1


def test_known_outcomes_are_gathered_from_the_contracts_on_this_app(tmp_path, monkeypatch):
    monkeypatch.setattr(start, "CONTRACTS", tmp_path)
    (tmp_path / "a.yaml").write_text(
        "vendor_app: demo-core-servicing\ncontract:\n  outcomes:\n"
        "    - {code: MEMBER_NOT_FOUND, meaning: none, resolver: member}\n")
    (tmp_path / "b.yaml").write_text(
        "vendor_app: demo-core-servicing\ncontract:\n  outcomes:\n"
        "    - {code: MEMBER_NOT_FOUND, meaning: dup, resolver: member}\n"
        "    - {code: NO_SAVINGS_ACCOUNT, meaning: none, resolver: member}\n")
    (tmp_path / "other.yaml").write_text(
        "vendor_app: some-other-app\ncontract:\n  outcomes:\n"
        "    - {code: ELSEWHERE, meaning: x, resolver: member}\n")
    codes = [o["code"] for o in start.known_outcomes("demo-core-servicing")]
    assert codes == ["MEMBER_NOT_FOUND", "NO_SAVINGS_ACCOUNT"]


def test_the_proposal_receives_the_known_outcomes(tmp_path, monkeypatch):
    monkeypatch.setattr(start, "CONTRACTS", tmp_path)
    (tmp_path / "a.yaml").write_text(
        "vendor_app: demo-core-servicing\ncontract:\n  outcomes:\n"
        "    - {code: NO_SAVINGS_ACCOUNT, meaning: none, resolver: member}\n")
    got = {}
    def propose(goal, app, **kw):
        got.update(kw); return spec_from_proposal(PROPOSAL, app)
    start.run(goal="x", ask=_scripted(["n"]), propose=propose,
              discover_fn=lambda r: pytest.fail("must not run"))
    assert [o["code"] for o in got["known_outcomes"]] == ["NO_SAVINGS_ACCOUNT"]


def test_not_approved_saves_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(start, "CONTRACTS", tmp_path)
    code = start.run(goal="read a balance", ask=_scripted(["n"]),
                     propose=lambda goal, app, **kw: spec_from_proposal(PROPOSAL, app),
                     discover_fn=lambda r: pytest.fail("must not run"))
    assert code == 0 and list(tmp_path.glob("*.yaml")) == []


# ── the second review: the Artifact, from the shipped discovery run ────────────

RUN = "evidence/01-discovery-goal-reached"      # the sub-account run: 2 consequential clicks + t_ok


def _sub_account_spec():
    return start.load_request("contracts/open_sub_account.yaml") if hasattr(start, "load_request") \
        else __import__("yaml").safe_load(open("contracts/open_sub_account.yaml"))


class _Ok:
    status = "succeeded"
    def __str__(self): return "succeeded"


class _Bad:
    status = "failed"
    def __str__(self): return "failed · target_not_found"


def test_the_review_writes_decisions_applies_them_and_saves_an_approved_artifact(tmp_path, monkeypatch):
    monkeypatch.setattr(start, "ARTIFACTS", tmp_path)
    import yaml
    spec = yaml.safe_load(open("contracts/open_sub_account.yaml"))
    seen = []
    def ask(prompt):
        seen.append(prompt)
        if "Review this artifact" in prompt: return "y"
        if "is this action safe" in prompt:
            return "n" if "t_continue" in prompt else "y"      # the commit stays consequential
        if "interruption" in prompt: return "y" if "'OK'" in prompt else "n"
        if "identifies it" in prompt: return "System notice"
        if "reuse watcher" in prompt: return "y"
        if "no watcher can recognise" in prompt: return "d"    # VALIDATION_REJECTED dropped
        if "page to open afterwards" in prompt: return ""            # take the default
        if "proves it happened" in prompt: return "{{nickname}}"
        if "approve as" in prompt: return "reviewer:nasi"
        if "second approver" in prompt: return "reviewer:sam"
        if "Watch it replay" in prompt: return "n"
        return ""
    verified = {}
    def fake_replay(art, inputs):
        verified["inputs"] = inputs; verified["status"] = art.capability.status
        return _Ok()
    code = start.review_artifact(spec, RUN, ask=ask, replay_fn=fake_replay)
    assert code == 0, seen
    d = yaml.safe_load((tmp_path / "open_sub_account.decisions.yaml").read_text())
    assert "t_continue" not in d["safe_targets"] and "t_sign_in" in d["safe_targets"]
    assert d["interruptions"][0]["target"] == "t_ok"
    assert {w["outcome"] for w in d["watchers"]} == {"MEMBER_NOT_FOUND", "NOT_AUTHORIZED"}
    assert d["keep_outcomes"] == ["MEMBER_NOT_FOUND", "NOT_AUTHORIZED"]
    assert d["approvals"] == ["reviewer:nasi", "reviewer:sam"]
    assert d["verify_effects"] == [{"target": "t_continue", "verify_effect": {
        "goto": "/members/{{member_number}}",
        "predicate": {"type": "text_present", "value": "{{nickname}}"}}}]
    assert verified["inputs"]["member_number"] == "12345"        # discovery used 54321
    out = yaml.safe_load((tmp_path / "open_sub_account.1.0.0.yaml").read_text())
    assert out["capability"]["status"] == "approved"
    assert "VALIDATION_REJECTED" not in {o["code"] for o in out["contract"]["outcomes"]}
    assert any(w["id"] == "w_system_notice" for w in out["watchers"])


def test_a_failed_verify_replay_refuses_and_keeps_the_decisions(tmp_path, monkeypatch):
    monkeypatch.setattr(start, "ARTIFACTS", tmp_path)
    import yaml
    spec = yaml.safe_load(open("contracts/open_sub_account.yaml"))
    def ask(prompt):
        if "is this action safe" in prompt: return "n" if "t_continue" in prompt else "y"
        if "interruption" in prompt: return "y" if "'OK'" in prompt else "n"
        if "identifies it" in prompt: return "System notice"
        if "no watcher can recognise" in prompt: return "d"
        if "page to open afterwards" in prompt: return ""
        if "proves it happened" in prompt: return "{{nickname}}"
        if "second approver" in prompt: return "reviewer:sam"
        return "y" if "?" in prompt else "reviewer:nasi"
    code = start.review_artifact(spec, RUN, ask=ask, replay_fn=lambda a, i: _Bad())
    assert code == 2
    assert (tmp_path / "open_sub_account.decisions.yaml").exists()
    assert not (tmp_path / "open_sub_account.1.0.0.yaml").exists()


def test_declining_the_review_leaves_the_draft_and_runs_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(start, "ARTIFACTS", tmp_path)
    import yaml
    spec = yaml.safe_load(open("contracts/open_sub_account.yaml"))
    code = start.review_artifact(spec, RUN, ask=lambda p: "n",
                                 replay_fn=lambda a, i: pytest.fail("must not run"))
    assert code == 0 and list(tmp_path.glob("*")) == []


def test_the_watch_step_replays_the_capability_just_approved(tmp_path, monkeypatch):
    monkeypatch.setattr(start, "ARTIFACTS", tmp_path)
    import yaml
    spec = yaml.safe_load(open("contracts/open_sub_account.yaml"))
    def ask(prompt):
        if "is this action safe" in prompt: return "n" if "t_continue" in prompt else "y"
        if "interruption" in prompt: return "y" if "'OK'" in prompt else "n"
        if "identifies it" in prompt: return "System notice"
        if "no watcher can recognise" in prompt: return "d"
        if "page to open afterwards" in prompt: return ""
        if "proves it happened" in prompt: return "{{nickname}}"
        if "second approver" in prompt: return "reviewer:sam"
        if "show the approved file" in prompt: return "n"
        if "Watch it replay" in prompt: return "y"
        return "y" if "?" in prompt else "reviewer:nasi"
    watched = {}
    start.review_artifact(spec, RUN, ask=ask, replay_fn=lambda a, i: _Ok(),
                          watch_fn=lambda cap, member, tenant: watched.update(cap=cap, member=member))
    assert watched == {"cap": "member.open_sub_account", "member": "54321"}   # the discovery member


def test_replay_inputs_are_filtered_to_the_contract():
    from cua.store import load_capability
    from tools.replay import inputs_for, parse_args
    art = load_capability("member.open_sub_account")
    assert inputs_for(art, "12345") == {"member_number": "12345", "account_type": "savings",
                                        "nickname": "Live demo"}
    assert inputs_for(art, "12345", {"nickname": "Mine", "bogus": "x"})["nickname"] == "Mine"
    assert "bogus" not in inputs_for(art, "12345", {"bogus": "x"})
    a = parse_args(["12345", "--capability", "member.read_savings_balance", "--headed"])
    assert (a.member, a.capability, a.headed, a.tenant) == ("12345", "member.read_savings_balance", True, "bank_a")


def test_replay_asks_which_capability_when_more_than_one_is_approved():
    from tools.replay import choose_capability
    asked = []
    picked = choose_capability(ask=lambda p: asked.append(p) or "member.read_savings_balance")
    assert picked == "member.read_savings_balance" and asked          # two approved on disk
    assert choose_capability(ask=lambda p: "1") == "member.open_sub_account"   # sorted: first
    assert choose_capability(ask=lambda p: "") == "member.open_sub_account"    # default


def test_an_approver_must_be_role_name_so_yes_is_not_a_signature():
    answers = iter(["yes", "y", "reviewer:nasi"])
    got = start._approver(lambda p: next(answers), "approve as: ", None)
    assert got == "reviewer:nasi"
    assert start._approver(lambda p: "", "approve as [reviewer:x]: ", "reviewer:x") == "reviewer:x"
