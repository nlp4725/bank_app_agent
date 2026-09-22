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
    def __init__(self, origin: str, headless: bool = True):
        self.origin = origin.rstrip("/")
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(headless=headless)
        # Hardening: no downloads, no extra windows, no permissions, fresh context.
        self._context = self._browser.new_context(accept_downloads=False)
        self._context.grant_permissions([])
        self.page = self._context.new_page()
        self.page.on("dialog", lambda d: d.dismiss())
        self._context.on("page", lambda p: p.close())

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

    def screenshot(self, path: str):
        self.page.screenshot(path=path)

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
            time.sleep(0.15)

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
            time.sleep(0.15)

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
