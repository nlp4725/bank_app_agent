"""The only module that touches the browser.

Everything above it works in terms of Targets, Predicates and Actions; everything
below is Playwright. That seam is what a DesktopSurface would implement later, and
it is asserted by a test: no other module may import playwright.
"""

import fnmatch
import time
from dataclasses import dataclass

from playwright.sync_api import sync_playwright

from .artifact import Target

INTERACTIVE_FALLBACK = "td, span, div, p, strong, b"


@dataclass
class Resolved:
    locator: object
    matched_by: str          # which rung found it
    rung_index: int


class Surface:
    def __init__(self, origin: str, headless: bool = True, allowed_origins: list[str] | None = None):
        self.origin = origin.rstrip("/")
        self.allowed_origins = [o.rstrip("/") for o in (allowed_origins or [self.origin])]
        self.blocked_requests: list[str] = []
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(headless=headless)
        # Hardening: no downloads, no extra windows, no permissions, fresh context.
        self._context = self._browser.new_context(accept_downloads=False)
        self._context.grant_permissions([])
        self.page = self._context.new_page()
        self.page.on("dialog", lambda d: d.dismiss())
        self._context.on("page", lambda p: p.close())
        # The allowlist is enforced on every request the browser makes, including the
        # ones the page starts by itself: an <img> pointing off-site cannot leave.
        self._context.route("**/*", self._gate)

    def _gate(self, route, request):
        if any(request.url.startswith(o) for o in self.allowed_origins):
            route.continue_()
        else:
            self.blocked_requests.append(request.url)
            route.abort()

    def _tick(self, ms: int = 150):
        """Wait, while letting Playwright work.

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

    def screenshot(self, path: str, mask_targets: list | None = None, scale: str = "css"):
        """Paint over declared regions as the image is captured.

        Text redaction cannot clean pixels, so anything sensitive is masked at
        capture time rather than afterwards. Regions are Targets, so they are
        declared in the App Profile and reviewable there.
        """
        masks = []
        for target in (mask_targets or []):
            found = self.resolve(target, timeout_ms=0)
            if found is not None:
                masks.append(found.locator)
        self.page.screenshot(path=path, mask=masks, mask_color="#000000", scale=scale)

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
                    found = self._try_rung(scope, rung)
                    if found is not None:
                        return Resolved(found, rung.kind, index)
            if time.time() >= deadline:
                return None
            self._tick()

    def _try_rung(self, scope, rung):
        try:
            if rung.kind == "role_name":
                loc = scope.get_by_role(rung.role, name=rung.name, exact=True)
                return loc.first if loc.count() else None
            if rung.kind == "label_anchor":
                return self._by_anchor(scope, rung)
            if rung.kind == "picture":
                return None      # template matching: not implemented; falls through
        except Exception:
            return None
        return None

    def _by_anchor(self, scope, rung):
        """Find the words, then the nearest control in the given relation.

        Geometry, not DOM structure — the same idea works on a desktop accessibility
        tree or on OCR over a screenshot. See docs/targeting.md.
        """
        anchor = scope.get_by_text(rung.anchor, exact=True)
        if not anchor.count():
            return None
        a = anchor.first.bounding_box()
        if not a:
            return None

        candidates = scope.get_by_role(rung.role) if rung.role else scope.locator(INTERACTIVE_FALLBACK)
        best, best_score = None, float("inf")
        for i in range(min(candidates.count(), 200)):
            c = candidates.nth(i)
            try:
                b = c.bounding_box()
            except Exception:
                continue
            if not b or b["width"] == 0:
                continue
            if rung.role is None:
                try:
                    if not c.inner_text().strip() or c.inner_text().strip() == rung.anchor:
                        continue
                    if c.locator(INTERACTIVE_FALLBACK).count():
                        continue        # prefer the innermost element holding the text
                except Exception:
                    continue

            same_line = abs((b["y"] + b["height"] / 2) - (a["y"] + a["height"] / 2)) < max(a["height"], 14)
            dx = b["x"] - (a["x"] + a["width"])
            dy = b["y"] - (a["y"] + a["height"])
            if rung.relation == "right_of":
                score = dx if (same_line and dx >= -2) else float("inf")
            elif rung.relation == "below":
                overlap = not (b["x"] + b["width"] < a["x"] or b["x"] > a["x"] + a["width"])
                score = dy if (overlap and dy >= -2) else float("inf")
            else:  # nearest
                score = abs(dx) + abs(dy)
            if score < best_score:
                best, best_score = c, score
        return best

    # ── enumerating, for discovery ───────────────────────────────────────────

    INTERACTIVE = ("button", "textbox", "link", "combobox", "checkbox", "radio")

    def controls(self) -> list[dict]:
        """Every control a person could act on, main document and frames.

        Controls with no accessible name are the interesting ones: we annotate them
        with the nearest text to their left, which is what a human reads instead.
        """
        found = []
        for frame in self.page.frames:
            for role in self.INTERACTIVE:
                loc = frame.get_by_role(role)
                for i in range(min(loc.count(), 40)):
                    el = loc.nth(i)
                    try:
                        box = el.bounding_box()
                        if not box or box["width"] == 0:
                            continue
                        name = (el.get_attribute("aria-label")
                                or el.inner_text().strip()
                                or el.get_attribute("value") or "")
                        found.append({
                            "index": len(found) + 1,
                            "role": role,
                            "name": name,
                            "anchor": self.nearest_text(frame, box),
                            "is_password": (el.get_attribute("type") == "password"),
                            "frame_url": frame.url,
                            "box": box,
                            "locator": el,
                        })
                    except Exception:
                        continue
        return found

    def values(self, start_index: int) -> list[dict]:
        """Label/value pairs on the page: the things a `read` action needs.

        A balance or a confirmation number is a table cell, not a control. The model
        can see it in the screenshot, so it must be able to point at it too.
        """
        found = []
        for frame in self.page.frames:
            cells = frame.locator("td, th")
            for i in range(min(cells.count(), 120)):
                label = cells.nth(i)
                try:
                    text = label.inner_text().strip()
                    if (not text or len(text) > 40 or "\n" in text
                            or label.locator("td, input, button, a").count()):
                        continue
                    value = label.locator("xpath=following-sibling::*[1]")
                    if not value.count():
                        continue
                    shown = value.first.inner_text().strip()
                    if (not shown or len(shown) > 60 or "\n" in shown
                            or value.first.locator("input, button, a, td").count()):
                        continue
                    box = value.first.bounding_box()
                    if not box:
                        continue
                except Exception:
                    continue
                found.append({
                    "index": start_index + len(found),
                    "role": "text",
                    "name": "",
                    "anchor": text,
                    "text": shown,
                    "is_password": False,
                    "frame_url": frame.url,
                    "box": box,
                    "locator": value.first,
                })
        return found

    def nearest_text(self, frame, box) -> str | None:
        """The visible words closest to the left of a box, then above it.

        This is label_anchor in reverse: at record time we work out which caption a
        human would read for this control, so replay can find it the same way.
        """
        best, best_score = None, float("inf")
        cells = frame.locator("td, th, label, span, div, p, strong, b")
        for i in range(min(cells.count(), 250)):
            cell = cells.nth(i)
            try:
                if cell.locator("input, button, select, textarea, td, span, div").count():
                    continue          # innermost text holders only
                text = cell.inner_text().strip()
                if not text or len(text) > 40:
                    continue
                b = cell.bounding_box()
                if not b:
                    continue
            except Exception:
                continue
            same_line = abs((b["y"] + b["height"] / 2) - (box["y"] + box["height"] / 2)) < max(b["height"], 14)
            dx = box["x"] - (b["x"] + b["width"])
            if same_line and dx >= -2 and dx < best_score:
                best, best_score = text, dx
        return best

    def describe(self, control: dict) -> dict:
        """Turn the control that was just acted on into durable Target descriptors.

        A value read from a table cell has no ARIA role — "text" is our own label for
        it — so its rung carries no role and is resolved as "the nearest thing to the
        right of these words".
        """
        role = None if control["role"] == "text" else control["role"]
        rungs = []
        if control["name"] and role:
            rungs.append({"kind": "role_name", "role": role, "name": control["name"]})
        if control["anchor"]:
            rungs.append({"kind": "label_anchor", "anchor": control["anchor"],
                          "role": role, "relation": "right_of"})
        target = {"rungs": rungs}
        if "/" in control["frame_url"] and control["frame_url"] != self.page.url:
            tail = control["frame_url"].rsplit("/", 1)[-1]
            target["frame"] = {"url_contains": f"/{tail}"}
        return target

    def crop(self, control: dict, path: str):
        """A small picture of one control: the last rung of a ladder."""
        try:
            control["locator"].screenshot(path=path)
            return path
        except Exception:
            return None

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

    # ── predicates ───────────────────────────────────────────────────────────

    def holds(self, predicate, artifact, timeout_ms: int = 4000) -> bool:
        deadline = time.time() + timeout_ms / 1000
        while True:
            if self._holds_once(predicate, artifact):
                return True
            if time.time() >= deadline:
                return False
            self._tick()

    def _holds_once(self, predicate, artifact) -> bool:
        kind = predicate.type
        if kind == "text_present":
            return predicate.value in self.text()
        if kind == "url_matches":
            return fnmatch.fnmatch(self.url, f"*{predicate.pattern}*")
        if kind == "element_present":
            target = artifact.targets.get(predicate.target)
            return target is not None and self.resolve(target, timeout_ms=0) is not None
        if kind == "field_value":
            target = artifact.targets.get(predicate.target)
            found = self.resolve(target, timeout_ms=0) if target else None
            if found is None:
                return False
            value = found.locator.input_value()
            if predicate.non_empty:
                return bool(value)
            return value == predicate.equals
        if kind == "all":
            return all(self._holds_once(p, artifact) for p in predicate.of)
        if kind == "any":
            return any(self._holds_once(p, artifact) for p in predicate.of)
        return False
