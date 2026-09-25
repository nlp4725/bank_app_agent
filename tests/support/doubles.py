"""Stand-ins for the things a test would otherwise need running: a browser, a model,
a verify-replay, a person at the prompt. Each is the smallest class the seam it stands
behind asks for — which is the point of having the seam."""

import re

from cua.discovery import Turn

# ── a Surface that is a page description rather than a browser ───────────────

class ScriptedSurface:
    """A Surface that is a page description rather than a browser."""

    def __init__(self, text="", url="http://app/", present=(), values=None, targets=None):
        self._text, self.url = text, url
        self._present = set(present)
        self._values = values or {}
        # The seam hands a Target, not its name: the stand-in maps back the way a
        # driver would, by which Target object it was given.
        self._names = {id(t): n for n, t in (targets or {}).items()}
        self.waits = 0
        self.went_to = []

    def text(self):
        return self._text

    def wait(self, ms=150):
        self.waits += 1

    def goto(self, path):
        self.went_to.append(path)
        self.url = "http://app" + path

    def resolve(self, target, timeout_ms=0):
        name = self._names.get(id(target))
        return name if name in self._present else None

    def value_of(self, resolved):
        return self._values.get(resolved, "")


# ── a model that answers each turn from a list ───────────────────────────────

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


def observation_text(messages) -> str:
    return next(b["text"] for b in messages[-1]["content"] if b.get("type") == "text")


def control_numbered(messages, caption: str) -> int:
    """The [n] of the control the observation lists beside `caption`."""
    for line in observation_text(messages).splitlines():
        if f'near text: "{caption}"' in line:
            return int(re.match(r"\[(\d+)\]", line).group(1))
    raise AssertionError(f"no control near {caption!r} in:\n{observation_text(messages)}")


# ── a verify-replay that already knows its answer ────────────────────────────

class VerifyOk:
    status = "succeeded"
    def __str__(self): return "succeeded"


class VerifyBad:
    status = "failed"
    def __str__(self): return "failed · target_not_found"


# ── a person at the prompt, answering from a list ────────────────────────────

def scripted_answers(answers):
    answers = iter(answers)
    return lambda prompt: next(answers)
