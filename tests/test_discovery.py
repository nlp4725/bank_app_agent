"""The Discovery loop, driven by a scripted model: the first tests of it that need no key.

What the model says is data the loop checks and acts on; these tests script that data
and assert on what the loop did — the ending it chose, what it wrote down, and what
it never wrote down.
"""

import json
import re
from pathlib import Path

from cua.discovery import DiscoveryRequest, ToolCall, Turn, discover
from cua.evidence import PROTECTED

VENDOR_APP = "demo-core-servicing"
CONTRACT = {"inputs": {}, "outputs": {},
            "outcomes": [{"code": "MEMBER_NOT_FOUND", "meaning": "No such member.",
                          "resolver": "member"}]}


class Scripted:
    """Answers each turn from a list. An entry is a ToolCall, None (no tool call), or
    a function of the transcript that returns one of those — for a turn that has to
    read the observation to know which control to name."""

    def __init__(self, answers):
        self.answers = list(answers)
        self.seen = []

    def next_action(self, messages, **_):
        self.seen.append(list(messages))       # the transcript as it stood when asked
        answer = self.answers.pop(0)
        if callable(answer):
            answer = answer(messages)
        if answer is None:
            return Turn([{"type": "text", "text": "..."}], None, [])
        block = {"type": "tool_use", "id": f"call_{len(self.seen)}", "name": answer.name,
                 "input": answer.input}
        return Turn([block], answer, [])


def request(origin, tmp_path, model, **overrides):
    fields = dict(goal="find member 99999", vendor_app=VENDOR_APP, role="account_opener",
                  contract=CONTRACT, example_values={}, origin=origin,
                  evidence_root=str(tmp_path), compile_draft=False, model=model)
    fields.update(overrides)
    return DiscoveryRequest(**fields)


def observation_text(messages) -> str:
    return next(b["text"] for b in messages[-1]["content"] if b.get("type") == "text")


def control_numbered(messages, caption: str) -> int:
    """The [n] of the control the observation lists beside `caption`."""
    for line in observation_text(messages).splitlines():
        if f'near text: "{caption}"' in line:
            return int(re.match(r"\[(\d+)\]", line).group(1))
    raise AssertionError(f"no control near {caption!r} in:\n{observation_text(messages)}")


def test_a_business_outcome_the_model_reports_ends_the_run_with_it(bank_app, tmp_path):
    model = Scripted([ToolCall("c1", "report_outcome",
                               {"code": "MEMBER_NOT_FOUND", "quote": "No records found",
                                "reason": "the app said so"})])
    result = discover(request(bank_app, tmp_path, model))
    assert result.ending == "report_outcome"
    assert result.outcome == "MEMBER_NOT_FOUND" and result.detail == "No records found"
    assert result.turns == 1
    events = [json.loads(l)["event"] for l in (Path(result.trace_dir) / "trail.jsonl").read_text().splitlines()]
    assert events[:3] == ["observed", "proposed", "ended"]


def test_a_model_that_makes_no_progress_is_stuck_and_told_so_each_turn(bank_app, tmp_path):
    """Two empty answers, each met with the one-tool-call instruction; the third look at
    the same screen is what ends it — the screen check runs before the model is asked."""
    model = Scripted([None, None, None])
    result = discover(request(bank_app, tmp_path, model))
    assert result.ending == "stuck_detected" and result.detail == "the same screen three times"
    assert result.turns == 3
    assert len(model.seen) == 2, "the third turn ended before the model was asked"
    assert model.seen[1][-2]["content"] == "Answer with exactly one tool call."


def test_a_secret_the_model_asks_for_is_typed_but_never_written_down(bank_app, tmp_path):
    model = Scripted([
        lambda messages: ToolCall("c1", "type", {"element": control_numbered(messages, "User ID"),
                                                 "value": None, "secret": "login_username",
                                                 "reason": "sign in"}),
        ToolCall("c2", "goal_reached", {"reason": "done"}),
    ])
    result = discover(request(bank_app, tmp_path, model))
    assert result.ending == "goal_reached"
    (action,) = result.actions
    assert action["action"] == "type" and action["value_ref"] == "login_username"
    assert action["value"] == PROTECTED
    written = "".join(p.read_text() for p in Path(result.trace_dir).glob("*.json*"))
    assert "svc_officer" not in written, "the resolved secret reached the evidence"
    assert "login_username" in written, "the reference, not the value, is what is recorded"


def test_the_model_is_told_which_secrets_and_outcomes_exist(bank_app, tmp_path):
    seen = {}

    class Recording(Scripted):
        def next_action(self, messages, **kw):
            seen.update(kw)
            return super().next_action(messages, **kw)

    discover(request(bank_app, tmp_path, Recording([ToolCall("c1", "give_up", {"reason": "x"})])))
    assert seen["secret_names"] == ["login_username", "login_password"]
    assert seen["outcome_codes"] == ["MEMBER_NOT_FOUND"]
    assert seen["output_names"] == []
