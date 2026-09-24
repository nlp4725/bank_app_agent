"""What a replay is given, and the shapes of the four things it is given through.

The Protocols are the seams. Each is what the engine actually calls and nothing
more, so a scripted Surface, a test secrets provider, a callback Operator and a
silent Narrator are all one small class away. The boundary test derives its
"acting interface" from `ActingSurface`, so the engine cannot quietly reach past it.
"""

from dataclasses import dataclass
from typing import Any, Protocol

from ..domain.artifact import Target


class ActingSurface(Protocol):
    """Act and observe: the whole of what the Replay Engine needs from a session."""

    origin: str
    allowed_origins: list[str]
    blocked_requests: list[str]

    @property
    def url(self) -> str: ...
    def goto(self, path: str) -> None: ...
    def text(self) -> str: ...
    def wait(self, ms: int = 150) -> None: ...
    def close(self) -> None: ...
    def screenshot(self, path: str, mask_targets: list | None = None, scale: str = "css",
                   readable_anchors: set | None = None, sensitive_text: tuple = ()) -> None: ...
    def resolve(self, target: Target, timeout_ms: int = 5000) -> Any | None: ...
    def click(self, resolved: Any) -> None: ...
    def type(self, resolved: Any, value: str) -> None: ...
    def select(self, resolved: Any, value: str) -> None: ...
    def read(self, resolved: Any) -> str: ...
    def value_of(self, resolved: Any) -> str: ...
    def frame_urls(self) -> list[str]: ...


class SecretsProvider(Protocol):
    """A secret by name, at the moment of use. Raises MissingSecret otherwise."""

    def get(self, name: str) -> str: ...


class Operator(Protocol):
    """A person on shift: given the intervention and the live session, answers
    "resume" or "abort" — or nothing, having acted, and the screen decides."""

    def __call__(self, intervention: Any, surface: ActingSurface) -> str | None: ...


class Narrator(Protocol):
    """How a run looks to someone watching it. See narration.py for the two."""

    slow_mo_ms: int

    def transition(self, transition: Any, found: Any) -> None: ...
    def linger(self, surface: ActingSurface) -> None: ...


def members(protocol: type) -> set[str]:
    """The names a Protocol asks for: its methods, properties and annotated fields."""
    return ({n for n in vars(protocol) if not n.startswith("_")}
            | set(getattr(protocol, "__annotations__", {})))


@dataclass
class RunContext:
    origin: str
    attended: bool = False
    tenant: str = "bank_a"
    secrets: SecretsProvider | None = None      # defaults to the Role's Service Account
    evidence_root: str = "runs"
    headless: bool = True
    # An Operator: called when the run escalates and a person is on shift. Given the
    # intervention and the live session, it returns "resume" or "abort". Absent, the
    # run waits for a decision file, which is what an operator console would write.
    operator: Operator | None = None
    operator_timeout_s: float = 120.0
    # A Tenant Overlay: appearance only. Linted before it is applied, so a patch that
    # tried to add a transition, change the contract or widen needs is refused here
    # rather than quietly taking effect.
    overlay: dict | None = None
    # How the run looks to a person watching it — pacing, narration, whether the
    # browser is left open. Demo ergonomics, behind their own seam: see cua/narration.
    narrator: Narrator | None = None
