"""Start with a goal: the proposal is validated, the conversation is scripted.

No model and no browser: `propose` and `discover` are handed in, so what is tested is
the shape the model must return and what the Reviewer is asked.
"""

import pytest

from cua.discovery import ProposalError, spec_from_proposal
from tests.support.doubles import VerifyBad, VerifyOk, scripted_answers
from tests.support.proposal import PROPOSAL
from tools import start
from tools.authoring import interview, review
from tools.discovery import contract


def test_the_conversation_asks_goal_then_values_then_confirms_and_runs(tmp_path, monkeypatch):
    monkeypatch.setattr(contract, "CONTRACTS", tmp_path)
    seen = {}

    def fake_discover(request):
        seen["request"] = request
        class R:
            ending, outputs, trace_dir, draft, suggestions, actions = (
                "goal_reached", {"savings_balance": "$1.00"}, str(tmp_path), None, [], [])
            def __str__(self): return "ok"
        return R()

    code = start.run(ask=scripted_answers(["read the savings balance of a member", "y", "12345",
                                           "99999", "n"]),
                     propose=lambda goal, app, **kw: spec_from_proposal(PROPOSAL, app),
                     discover_fn=fake_discover)
    assert code == 0
    r = seen["request"]
    assert r.goal == "Look up member 12345 and read their savings balance"
    assert r.role == "balance_reader" and r.capability_id == "member.read_savings_balance"
    assert r.example_values == {"member_number": "12345"}
    assert r.headless is True                       # answered "n" to watching
    saved = __import__("yaml").safe_load((tmp_path / "read_savings_balance.yaml").read_text())
    assert saved["outcome_examples"] == {"MEMBER_NOT_FOUND": {"member_number": "99999"}}


def test_a_value_that_breaks_the_contract_is_asked_again(tmp_path, monkeypatch):
    monkeypatch.setattr(contract, "CONTRACTS", tmp_path)
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
    monkeypatch.setattr(contract, "CONTRACTS", tmp_path)
    code = start.run(goal="read a balance", ask=scripted_answers(["e"]),
                     propose=lambda goal, app, **kw: spec_from_proposal(PROPOSAL, app),
                     discover_fn=lambda r: pytest.fail("must not run"))
    assert code == 0
    saved = (tmp_path / "read_savings_balance.yaml").read_text()
    assert "member.read_savings_balance" in saved and "balance_reader" in saved


def test_a_failed_proposal_ends_the_conversation_cleanly():
    def bad(goal, app, **kw):
        raise ProposalError("nope")
    assert start.run(goal="x", ask=scripted_answers([]), propose=bad,
                     discover_fn=lambda r: pytest.fail("must not run")) == 1


def test_known_outcomes_are_gathered_from_the_contracts_on_this_app(tmp_path, monkeypatch):
    monkeypatch.setattr(contract, "CONTRACTS", tmp_path)
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
    codes = [o["code"] for o in contract.known_outcomes("demo-core-servicing")]
    assert codes == ["MEMBER_NOT_FOUND", "NO_SAVINGS_ACCOUNT"]


def test_the_proposal_receives_the_known_outcomes(tmp_path, monkeypatch):
    monkeypatch.setattr(contract, "CONTRACTS", tmp_path)
    (tmp_path / "a.yaml").write_text(
        "vendor_app: demo-core-servicing\ncontract:\n  outcomes:\n"
        "    - {code: NO_SAVINGS_ACCOUNT, meaning: none, resolver: member}\n")
    got = {}
    def propose(goal, app, **kw):
        got.update(kw); return spec_from_proposal(PROPOSAL, app)
    start.run(goal="x", ask=scripted_answers(["n"]), propose=propose,
              discover_fn=lambda r: pytest.fail("must not run"))
    assert [o["code"] for o in got["known_outcomes"]] == ["NO_SAVINGS_ACCOUNT"]


def test_not_approved_saves_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(contract, "CONTRACTS", tmp_path)
    code = start.run(goal="read a balance", ask=scripted_answers(["n"]),
                     propose=lambda goal, app, **kw: spec_from_proposal(PROPOSAL, app),
                     discover_fn=lambda r: pytest.fail("must not run"))
    assert code == 0 and list(tmp_path.glob("*.yaml")) == []


# ── the second review: the Artifact, from the shipped discovery run ────────────


RUN = "evidence/01-discovery-goal-reached"      # the sub-account run: 2 consequential clicks + t_ok


def _sub_account_spec():
    return __import__("yaml").safe_load(open("contracts/open_sub_account.yaml"))


def test_the_review_writes_decisions_applies_them_and_saves_an_approved_artifact(tmp_path, monkeypatch):
    monkeypatch.setattr(review, "ARTIFACTS", tmp_path)
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
        return VerifyOk()
    code = review.review_artifact(spec, RUN, ask=ask, replay_fn=fake_replay)
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
    monkeypatch.setattr(review, "ARTIFACTS", tmp_path)
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
    code = review.review_artifact(spec, RUN, ask=ask, replay_fn=lambda a, i: VerifyBad())
    assert code == 2
    assert (tmp_path / "open_sub_account.decisions.yaml").exists()
    assert not (tmp_path / "open_sub_account.1.0.0.yaml").exists()


def test_declining_the_review_leaves_the_draft_and_runs_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(review, "ARTIFACTS", tmp_path)
    import yaml
    spec = yaml.safe_load(open("contracts/open_sub_account.yaml"))
    code = review.review_artifact(spec, RUN, ask=lambda p: "n",
                                 replay_fn=lambda a, i: pytest.fail("must not run"))
    assert code == 0 and list(tmp_path.glob("*")) == []


def test_the_watch_step_replays_the_capability_just_approved(tmp_path, monkeypatch):
    monkeypatch.setattr(review, "ARTIFACTS", tmp_path)
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
    review.review_artifact(spec, RUN, ask=ask, replay_fn=lambda a, i: VerifyOk(),
                          watch_fn=lambda cap, member, tenant: watched.update(cap=cap, member=member))
    assert watched == {"cap": "member.open_sub_account", "member": "54321"}   # the discovery member


def test_replay_inputs_are_filtered_to_the_contract():
    from cua.governance.store import load_capability
    from tools.replay import inputs_for, parse_args
    art = load_capability("member.open_sub_account")
    assert inputs_for(art, "12345") == {"member_number": "12345", "account_type": "savings",
                                        "nickname": "Live demo"}
    assert inputs_for(art, "12345", {"nickname": "Mine", "bogus": "x"})["nickname"] == "Mine"
    assert "bogus" not in inputs_for(art, "12345", {"bogus": "x"})
    a = parse_args(["12345", "--capability", "member.read_savings_balance", "--headed", "--slowmo", "2000"])
    assert (a.member, a.capability, a.headed, a.tenant, a.slowmo) == (
        "12345", "member.read_savings_balance", True, "bank_a", 2000)


def test_replay_asks_which_capability_when_more_than_one_is_approved():
    from tools.replay import choose_capability
    asked = []
    picked = choose_capability(ask=lambda p: asked.append(p) or "member.read_savings_balance")
    assert picked == "member.read_savings_balance" and asked          # two approved on disk
    assert choose_capability(ask=lambda p: "1") == "member.open_sub_account"   # sorted: first
    assert choose_capability(ask=lambda p: "") == "member.open_sub_account"    # default


def test_an_approver_must_be_role_name_so_yes_is_not_a_signature():
    answers = iter(["yes", "y", "reviewer:nasi"])
    got = interview.ask_approver(lambda p: next(answers), "approve as: ", None)
    assert got == "reviewer:nasi"
    assert interview.ask_approver(lambda p: "", "approve as [reviewer:x]: ", "reviewer:x") == "reviewer:x"


def test_the_watch_step_finds_an_artifact_approved_into_an_empty_store(tmp_path, monkeypatch):
    """The store was read during the interview, before the approved file existed.

    With nothing to borrow, every outcome is dropped — which must leave a contract
    with none, not one with all of them and nothing to produce them."""
    import yaml
    from pathlib import Path
    from cua.governance.store import load_capability
    from cua.settings import settings
    (tmp_path / "config").symlink_to(Path("config").resolve())
    monkeypatch.setattr(settings, "root", tmp_path)
    monkeypatch.setattr(review, "ARTIFACTS", tmp_path / "artifacts")
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
    code = review.review_artifact(
        spec, RUN, ask=ask, replay_fn=lambda a, i: VerifyOk(),
        watch_fn=lambda cap, member, tenant: watched.update(art=load_capability(cap)))
    assert code == 0
    assert watched["art"].capability.status == "approved"


# ── outcomes learnt by probing, not typed ─────────────────────────────────────

def test_outcome_examples_already_saved_are_not_asked_again(tmp_path, monkeypatch):
    monkeypatch.setattr(contract, "CONTRACTS", tmp_path)
    spec = spec_from_proposal(PROPOSAL, "demo-core-servicing")
    spec["example_values"] = {"member_number": "12345"}
    spec["outcome_examples"] = {"MEMBER_NOT_FOUND": {"member_number": "99999"}}
    contract.save(spec)
    fresh = spec_from_proposal(PROPOSAL, "demo-core-servicing")      # proposed again
    asked = contract.ask_outcome_examples(fresh, ask=lambda p: pytest.fail(f"asked: {p}"))
    assert asked == {"MEMBER_NOT_FOUND": {"member_number": "99999"}}


def test_each_outcome_with_an_example_is_probed_and_recorded_beside_the_run(tmp_path):
    import json
    spec = yaml_spec("contracts/read_savings_balance.yaml")
    requests = []
    def fake_discover(request):
        requests.append(request)
        class R:
            trace_dir = str(tmp_path / f"disc_{len(requests)}")
            def __str__(self): return "report_outcome"
        return R()
    probes = start.probe_outcomes(spec, {"member_number": "12345"}, str(tmp_path),
                                  tenant="bank_a", headed=False, slowmo=0,
                                  discover_fn=fake_discover)
    assert [r.example_values["member_number"] for r in requests] == ["99999", "22222"]
    assert all(r.compile_draft is False for r in requests)         # a probe is not a capability
    assert json.loads((tmp_path / review.PROBES).read_text()) == probes
    assert set(probes) == {"MEMBER_NOT_FOUND", "NOT_AUTHORIZED"}


def test_the_review_offers_the_learnt_watcher_instead_of_asking_for_text(tmp_path, monkeypatch):
    import json, shutil
    monkeypatch.setattr(review, "ARTIFACTS", tmp_path / "artifacts")
    run = tmp_path / "happy"
    shutil.copytree(RUN, run)
    (run / review.PROBES).write_text(json.dumps(
        {"MEMBER_NOT_FOUND": "evidence/02-discovery-business-outcome"}))
    spec = yaml_spec("contracts/open_sub_account.yaml")
    prompts = []
    def ask(prompt):
        prompts.append(prompt)
        if "MEMBER_NOT_FOUND: learnt from" in prompt: return "y"
        if "reuse watcher" in prompt: return "n"
        if "no watcher can recognise" in prompt: return "d"
        if "is this action safe" in prompt: return "n" if "t_continue" in prompt else "y"
        if "interruption" in prompt: return "y" if "'OK'" in prompt else "n"
        if "identifies it" in prompt: return "System notice"
        if "page to open afterwards" in prompt: return ""
        if "proves it happened" in prompt: return "{{nickname}}"
        if "second approver" in prompt: return "reviewer:sam"
        if "Watch it replay" in prompt or "show the approved" in prompt: return "n"
        return "y" if "?" in prompt else "reviewer:nasi"
    code = review.review_artifact(spec, str(run), ask=ask, replay_fn=lambda a, i: VerifyOk())
    assert code == 0, prompts
    assert not any("MEMBER_NOT_FOUND: no watcher" in p for p in prompts)
    d = yaml_spec(str(tmp_path / "artifacts" / "open_sub_account.decisions.yaml"))
    learnt = next(w for w in d["watchers"] if w["outcome"] == "MEMBER_NOT_FOUND")
    assert learnt["trigger"] == {"type": "text_present", "value": "No records found"}
    assert learnt["provenance"] == "discovery:02-discovery-business-outcome"


def yaml_spec(path):
    import yaml
    return yaml.safe_load(open(path))
