"""The only module that touches the browser.

Everything above it works in terms of Targets, Predicates and Actions; everything
below is Playwright. That seam is what a DesktopSurface would implement later, and
it is asserted by a test: no other module may import playwright.

Two callers, two interfaces over one driver:

    Surface           act and observe — what the Replay Engine needs, and the whole
                      of what a scripted stand-in has to provide
    RecordingSurface  enumerate and describe — what a Discovery Run needs at record
                      time, and what replay never asks for

They are split because neither caller uses the other's half, and because a union
interface is what let a driver object leak upwards: the engine reached for
`surface.page.frames`, and discovery built a `Resolved` around a raw locator.
"""

import re
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Any

from playwright.sync_api import sync_playwright

from ..domain.artifact import Target
from . import locate, screen


@dataclass
class Resolved:
    locator: Any             # the driver's handle; nothing above this package touches it
    matched_by: str          # which rung found it
    rung_index: int


class Surface:
    def __init__(self, origin: str, headless: bool = True, allowed_origins: list[str] | None = None,
                 slow_mo_ms: int = 0):
        self.origin = origin.rstrip("/")
        self.allowed_origins = [o.rstrip("/") for o in (allowed_origins or [self.origin])]
        self.blocked_requests: list[str] = []
        self._pw = sync_playwright().start()
        # slow_mo is for a human watching: it paces every action so the run is legible.
        self._browser = self._pw.chromium.launch(
            headless=headless, slow_mo=slow_mo_ms,
            args=[] if headless else ["--window-position=60,60", "--window-size=1150,900"])
        # Hardening: no downloads, no extra windows, no permissions, fresh context.
        self._context = self._browser.new_context(accept_downloads=False,
                                                  viewport={"width": 1100, "height": 800})
        self._context.grant_permissions([])
        self.page = self._context.new_page()
        self.page.on("dialog", lambda d: d.dismiss())
        self._context.on("page", lambda p: p.close())
        # The allowlist is enforced on every request the browser makes, including the
        # ones the page starts by itself: an <img> pointing off-site cannot leave.
        self._context.route("**/*", self._gate)
        if not headless:
            self._bring_to_front()

    def _bring_to_front(self):
        """A watched run is no use behind the terminal window."""
        try:
            self.page.bring_to_front()
        except Exception:
            pass
        if sys.platform == "darwin":
            subprocess.run(["osascript", "-e",
                            'tell application "System Events" to set frontmost of '
                            'the first process whose name contains "Chromium" to true'],
                           capture_output=True)

    def _gate(self, route, request):
        if any(request.url.startswith(o) for o in self.allowed_origins):
            route.continue_()
        else:
            self.blocked_requests.append(request.url)
            route.abort()

    def wait(self, ms: int = 150):
        """Wait, while letting the driver work.

        Part of the interface, not an internal: the Replay Engine paces an escalation
        with it and the Predicate evaluator polls with it.

        A plain time.sleep() blocks the driver's event loop, so route handlers never
        run — and with request interception on, an iframe request is never let
        through and the frame stays empty forever. Poll through the browser instead.
        """
        try:
            self.page.wait_for_timeout(ms)
        except Exception:
            time.sleep(ms / 1000)

    def close(self):
        self._context.close()
        self._browser.close()
        self._pw.stop()

    # ── navigation ───────────────────────────────────────────────────────────

    def goto(self, path: str):
        self.page.goto(self.origin + path, wait_until="domcontentloaded")

    @property
    def url(self) -> str:
        return self.page.url

    def text(self) -> str:
        """All visible text, main document and frames — what a person would read."""
        chunks = []
        for frame in self.page.frames:
            try:
                chunks.append(frame.locator("body").inner_text())
            except Exception:
                pass
        return "\n".join(chunks)

    def screenshot(self, path: str, mask_targets: list | None = None, scale: str = "css",
                   readable_anchors: set | None = None, sensitive_text: tuple = ()):
        """Paint over what must not be in the picture, as the image is captured.

        Text redaction cannot clean pixels, so masking happens at capture time rather
        than afterwards. Three kinds of region, all declared in the App Profile:
        `mask_targets` (Sensitive Regions, by Target); every value cell whose caption is
        not in `readable_anchors` — the same default-deny the text channel applies, so a
        value the model may not read in text is not visible to it in pixels either; and
        `sensitive_text`, patterns for on-screen text that is not a value cell (a member
        number in a heading). Controls are never masked: the model must see what it acts on.
        """
        masks: list[Any] = []
        for target in (mask_targets or []):
            found = self.resolve(target, timeout_ms=0)
            if found is not None:
                masks.append(found.locator)
        if readable_anchors is not None:
            for cell in self.values(0):
                if cell["anchor"] not in readable_anchors:
                    masks.append(cell["locator"])
        for pattern in sensitive_text:
            rx = re.compile(pattern)
            for frame in self.page.frames:
                try:
                    hits = frame.get_by_text(rx)
                    for i in range(min(hits.count(), 20)):
                        masks.append(hits.nth(i))
                except Exception:
                    continue
        self.page.screenshot(path=path, mask=masks, mask_color="#000000",
                             scale=scale)  # type: ignore[arg-type]  # "css" | "device", by contract

    # ── resolving a Target ───────────────────────────────────────────────────

    def scope(self, target: Target):
        if target.frame is None:
            return self.page
        for frame in self.page.frames:
            if target.frame.url_contains in frame.url:
                return frame
        return None

    def resolve(self, target: Target, timeout_ms: int = 5000) -> Resolved | None:
        """Try each rung in order. Records which one matched; never guesses."""
        deadline = time.time() + timeout_ms / 1000
        while True:
            scope = self.scope(target)
            if scope is not None:
                for index, rung in enumerate(target.rungs):
                    found = locate.try_rung(scope, rung)
                    if found is not None:
                        return Resolved(found, rung.kind, index)
            if time.time() >= deadline:
                return None
            self.wait()

    # ── enumerating, for discovery ───────────────────────────────────────────

    # ── enumerating, for discovery ───────────────────────────────────────────
    #
    # The logic is in screen.py, over a page; these are the driver's handles to it.

    def controls(self) -> list[dict]:
        return screen.controls(self.page)

    def values(self, start_index: int) -> list[dict]:
        return screen.values(self.page, start_index)

    def describe(self, control: dict) -> dict:
        return screen.describe(control, self.page.url)

    def crop(self, control: dict, path: str):
        return screen.crop(control, path)

    # ── acting ───────────────────────────────────────────────────────────────

    def click(self, resolved: Resolved):
        resolved.locator.click()
        self.page.wait_for_load_state("domcontentloaded")

    def type(self, resolved: Resolved, value: str):
        resolved.locator.fill(value)

    def select(self, resolved: Resolved, value: str):
        resolved.locator.select_option(value)

    def read(self, resolved: Resolved) -> str:
        return resolved.locator.inner_text().strip()

    def value_of(self, resolved: Resolved) -> str:
        """What a field currently holds. Exposed so nothing above this module has to
        hold a driver object to ask."""
        try:
            return resolved.locator.input_value()
        except Exception:
            return ""

    def frame_urls(self) -> list[str]:
        """The documents on the page, for evidence when a Checkpoint is missed."""
        return [f.url for f in self.page.frames]

