"""The Predicate vocabulary: rendering, Target lookup and evaluation, in one place.

Every Checkpoint, Watcher trigger, Precondition and Verification Check is a Predicate
drawn from a closed set of four, plus `all` / `any`. Adding one to the vocabulary
means editing the shape in `artifact.py` and the case below — and nothing else. It
used to mean three modules, one of which enumerated a Predicate's fields by name, so
a new field silently stopped having its placeholders filled.

This module knows what an Artifact is; the Surface does not. It asks the Surface for
the three observations it needs — the visible text, the address, and whether a Target
resolves — which is what lets a Surface be scripted rather than a browser.
"""

import fnmatch
import time

from ..domain.placeholders import render


class Predicates:
    """Evaluates Predicates for one run: one Artifact, one set of inputs, one screen."""

    def __init__(self, surface, artifact, inputs: dict):
        self.surface = surface
        self.artifact = artifact
        self.inputs = inputs

    # ── rendering ────────────────────────────────────────────────────────────

    def rendered(self, predicate):
        """Fill placeholders anywhere in a Predicate.

        Every string field is walked, rather than a hardcoded list of field names, so
        a Predicate shape added later cannot be missed here.
        """
        data = predicate.model_copy(deep=True)
        for name in type(data).model_fields:
            current = getattr(data, name, None)
            if isinstance(current, str) and name != "type":
                setattr(data, name, render(current, self.inputs))
            elif isinstance(current, list) and current and hasattr(current[0], "model_copy"):
                setattr(data, name, [self.rendered(p) for p in current])
        return data

    # ── evaluation ───────────────────────────────────────────────────────────

    def holds(self, predicate, timeout_ms: int = 4000) -> bool:
        """Does this Predicate hold? Polls until it does, or until the deadline."""
        rendered = self.rendered(predicate)
        deadline = time.time() + timeout_ms / 1000
        while True:
            if self._once(rendered):
                return True
            if time.time() >= deadline:
                return False
            self.surface.wait()

    def _once(self, predicate) -> bool:
        kind = predicate.type
        if kind == "text_present":
            return predicate.value in self.surface.text()
        if kind == "url_matches":
            return fnmatch.fnmatch(self.surface.url, f"*{predicate.pattern}*")
        if kind == "element_present":
            return self._resolve(predicate.target) is not None
        if kind == "field_value":
            found = self._resolve(predicate.target)
            if found is None:
                return False
            value = self.surface.value_of(found)
            return bool(value) if predicate.non_empty else value == predicate.equals
        if kind == "all":
            return all(self._once(p) for p in predicate.of)
        if kind == "any":
            return any(self._once(p) for p in predicate.of)
        return False

    def _resolve(self, target_name: str):
        target = self.artifact.targets.get(target_name)
        return None if target is None else self.surface.resolve(target, timeout_ms=0)

    # ── a Predicate about somewhere else ─────────────────────────────────────

    def after_going_to(self, path: str, predicate, timeout_ms: int = 3000) -> bool:
        """Look, rather than acting again: the Verification Check's move."""
        if path:
            self.surface.goto(render(path, self.inputs))
        return self.holds(predicate, timeout_ms=timeout_ms)
