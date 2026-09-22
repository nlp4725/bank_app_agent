"""Control transfer: who is allowed to act on the live session, and when.

One holder at a time, enforced by a lease rather than by convention. The session is
the one the automation was already using — the Operator sees the browser mid-flow,
not a fresh one — and everything they do is recorded with their identity and without
their values.

    automation ──pause──► awaiting_operator ──take──► operator_in_control
         ▲                      │ timeout                      │ resume
         └──────── resuming ◄───┴──────────────────────────────┘
                     │ abort
                     ▼  aborted
"""

import json
import time
from dataclasses import dataclass, field
from pathlib import Path

AUTOMATION = "automation"
AWAITING_OPERATOR = "awaiting_operator"
OPERATOR_IN_CONTROL = "operator_in_control"
RESUMING = "resuming"
DONE = "done"

TRANSITIONS = {
    AUTOMATION: {AWAITING_OPERATOR, DONE},
    AWAITING_OPERATOR: {OPERATOR_IN_CONTROL, DONE},
    OPERATOR_IN_CONTROL: {RESUMING, DONE},
    RESUMING: {AUTOMATION, DONE},
}


class ControlError(Exception):
    pass


@dataclass
class Control:
    """The lease. Only the holder may act on the surface."""
    state: str = AUTOMATION
    holder: str = "automation"
    history: list = field(default_factory=list)

    def move(self, to: str, holder: str):
        if to not in TRANSITIONS.get(self.state, set()):
            raise ControlError(f"cannot move from {self.state!r} to {to!r}")
        self.history.append({"from": self.state, "to": to, "holder": holder,
                             "at": time.time()})
        self.state, self.holder = to, holder

    def assert_may_act(self, who: str):
        if self.holder != who:
            raise ControlError(f"{who!r} may not act: {self.holder!r} holds control")


@dataclass
class Intervention:
    """What the Operator is given. Enough to act without asking what happened."""
    run_id: str
    capability: str
    state: str
    reason: str
    watcher: str | None
    url: str
    screenshot: str
    raised_at: float = field(default_factory=time.time)

    def write(self, directory: Path) -> Path:
        path = Path(directory) / "intervention.json"
        path.write_text(json.dumps(self.__dict__, indent=2))
        return path


def wait_for_decision(directory: Path, timeout_s: float, poll) -> tuple[str, str]:
    """Wait for the Operator's decision file. Returns (decision, operator).

    A file rather than a socket because the point is the seam, not the transport:
    an operator console would write the same record.
    """
    path = Path(directory) / "decision.json"
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if path.exists():
            data = json.loads(path.read_text())
            return data.get("decision", "abort"), data.get("operator", "unknown")
        poll(500)
    return "timeout", ""


def observe_operator(surface, before_url: str) -> dict:
    """What changed while the Operator held control — never what they typed."""
    return {"url_before": before_url, "url_after": surface.url,
            "navigated": surface.url != before_url}
