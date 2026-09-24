"""Record-time view of the live session: enumerate and describe, never resolve or act
on a Target. What a Discovery Run needs and replay never asks for."""

from .driver import Resolved, Surface


class RecordingSurface:
    """Record-time view of the same live session.

    Enumerating a screen and describing what was acted on is the Recorder's work, not
    the engine's, so it lives behind its own interface. It holds a Surface rather than
    extending one: the acting half stays the smaller, substitutable interface.
    """

    def __init__(self, surface: Surface):
        self.surface = surface

    # what a Discovery Run needs from the acting half, named explicitly rather than
    # delegated wholesale — the point of the split is that the union is not on offer
    @property
    def url(self) -> str:
        return self.surface.url

    def goto(self, path: str):
        self.surface.goto(path)

    def text(self) -> str:
        return self.surface.text()

    def screenshot(self, path: str, mask_targets=None, scale: str = "css", **masking):
        # every masking argument the Redactor passes goes straight through
        return self.surface.screenshot(path, mask_targets, scale, **masking)

    def close(self):
        self.surface.close()

    # ── enumerating ──────────────────────────────────────────────────────────

    def controls(self) -> list[dict]:
        return self.surface.controls()

    def values(self, start_index: int) -> list[dict]:
        return self.surface.values(start_index)

    def describe(self, control: dict) -> dict:
        return self.surface.describe(control)

    def crop(self, control: dict, path: str):
        return self.surface.crop(control, path)

    def field_value(self, control: dict) -> str:
        """What an enumerated field currently holds, for the observation.

        The one read a Discovery Run makes of a control it did not act on. It goes
        through the acting half's `value_of` rather than the locator in the dict, so
        nothing above this module calls a driver method.
        """
        return self.surface.value_of(Resolved(control["locator"], "discovery", 0))

    # ── acting on something the model pointed at ─────────────────────────────

    def act_on(self, control: dict, kind: str, value: str | None = None) -> str | None:
        """Do one thing to an enumerated control.

        The Discovery Run names a control by its number in the observation; turning
        that into something the driver can act on is this module's job, so nothing
        above holds a driver object.
        """
        resolved = Resolved(control["locator"], "discovery", 0)
        if kind == "click":
            self.surface.click(resolved)
        elif kind == "type":
            self.surface.type(resolved, value)
        elif kind == "select":
            self.surface.select(resolved, value)
        elif kind == "read":
            return self.surface.read(resolved)
        else:
            raise ValueError(f"not an action: {kind!r}")
        return None
