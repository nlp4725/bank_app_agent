"""How a run looks to a person watching it — and nothing else.

Pacing a run so it can be followed, printing each transition, and holding the browser
open at the end are demo ergonomics, not part of executing an Artifact. They sat in
RunContext beside the run's real configuration, and the step loop called print().

Two adapters, which is what justifies the seam: Silent in tests and in production,
Console when somebody is watching.
"""


class Silent:
    """The default. A run that nobody is watching says nothing and waits for nothing."""

    slow_mo_ms = 0
    hold_open_s = 0

    def transition(self, transition, found):
        pass

    def linger(self, surface):
        pass


class Console(Silent):
    """A watched run: paced, narrated, and left on screen at the end."""

    def __init__(self, slow_mo_ms: int = 900, hold_open_s: float = 6):
        self.slow_mo_ms = slow_mo_ms
        self.hold_open_s = hold_open_s

    def transition(self, transition, found):
        action = transition.action
        value = getattr(action, "value", None) or (
            f"secret:{action.value_ref}" if getattr(action, "value_ref", None) else "")
        print(f"  {transition.from_state:16s} -> {transition.to_state:16s} "
              f"{action.type:6s} {action.target:24s} "
              f"{str(value)[:22]:24s} rung={found.matched_by} risk={transition.risk}",
              flush=True)

    def linger(self, surface):
        if self.hold_open_s:
            surface.wait(int(self.hold_open_s * 1000))


def from_env(env) -> Silent:
    """The narrator the demo tools want, from the six environment variables that used
    to be read inline, in one place that names them."""
    if env.get("HEADED") != "1" and env.get("VERBOSE") != "1":
        return Silent()
    return Console(slow_mo_ms=int(env.get("SLOWMO", "900" if env.get("HEADED") == "1" else "0")),
                   hold_open_s=float(env.get("HOLD", "6" if env.get("HEADED") == "1" else "0")))
