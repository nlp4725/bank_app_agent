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

from ..domain.errors import CuaError

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


class ControlError(CuaError):
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
    """What the Operator is given. Enough to act without asking what happened.

    Two kinds reach an Operator. An *escalation*: the run is stuck on a screen only
    a person can clear, and they take the live session. An *approval*: the run is
    about to perform a Consequential Action and will not without a person saying
    so; the request names the control and which rung found it, so a wrong Fallback
    Match is visible before the click.
    """
    run_id: str
    capability: str
    state: str
    reason: str
    watcher: str | None
    url: str
    screenshot: str
    instruction: str | None = None
    kind: str = "escalation"          # escalation | approval
    target: str | None = None         # approval: the control about to be acted on
    matched_by: str | None = None     # approval: which rung of its ladder found it
    raised_at: float = field(default_factory=time.time)


def wait_for_decision(directory: Path, timeout_s: float, poll,
                      cleared=None) -> tuple[str, str]:
    """Wait for the Operator — by decision, or by watching them fix it.

    Asking a person to press Resume after they have already done the work is a step
    that exists for the machine's benefit. If `cleared()` says the blocker is gone and
    the screen is somewhere the run recognises, control comes back on its own. The
    buttons stay, for the cases where nothing visibly changes and for Abort.
    """
    path = Path(directory) / "decision.json"
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if path.exists():
            data = json.loads(path.read_text())
            path.unlink()      # consumed: a run may ask more than once, each answered once
            return data.get("decision", "abort"), data.get("operator", "unknown")
        if cleared is not None and cleared():
            return "resume", "auto:blocker cleared"
        poll(500)
    return "timeout", ""


# What a run writes when it asks, and what settles the question. A request file stays
# in the run's directory after it is answered (it is evidence), and decision.json is
# deleted once read, so neither file alone says whether anyone is still waiting.
# The trail does: the last of these events is the answer.
REQUEST_FILES = {"approval_requested": "approval.json",
                 "intervention_raised": "intervention.json"}
SETTLED = {"operator_acted", "result"}
STALE_AFTER_S = 30 * 60      # a run killed while waiting never writes its result


def waiting_request(run_dir: Path, now: float | None = None,
                    stale_after_s: float = STALE_AFTER_S) -> Path | None:
    """The request this run is waiting on right now, or None.

    A run is waiting when its trail's last request is not followed by the Operator
    acting or by a result, nobody has written a decision the run has yet to read,
    and it was raised recently enough that the run could still be alive."""
    run_dir = Path(run_dir)
    trail = run_dir / "trail.jsonl"
    if not trail.exists() or (run_dir / "decision.json").exists():
        return None
    pending = None
    for line in trail.read_text().splitlines():
        try:
            event = json.loads(line).get("event")
        except ValueError:
            continue          # a line cut short by a crash
        if event in REQUEST_FILES:
            pending = REQUEST_FILES[event]
        elif event in SETTLED:
            pending = None
    if pending is None or not (run_dir / pending).exists():
        return None
    path = run_dir / pending
    now = time.time() if now is None else now
    return None if now - path.stat().st_mtime > stale_after_s else path


def open_requests(runs_root: Path = Path("runs"), now: float | None = None) -> list[Path]:
    """Every request a live run is waiting on, newest first."""
    runs_root = Path(runs_root)
    found = [p for d in runs_root.glob("run_*") if d.is_dir()
             if (p := waiting_request(d, now)) is not None]
    return sorted(found, key=lambda p: p.stat().st_mtime, reverse=True)


def observe_operator(surface, before_url: str) -> dict:
    """What changed while the Operator held control — never what they typed."""
    return {"url_before": before_url, "url_after": surface.url,
            "navigated": surface.url != before_url}
