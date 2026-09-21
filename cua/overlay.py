"""Tenant Overlays: may change how things look, never how they behave.

A patch that could add a step, alter the Contract or widen Needs would let a
cosmetic per-tenant file change what a reviewed capability does, so those keys
are rejected outright rather than merged. See CONTEXT.md, "Tenant Overlay".
"""

from .artifact import Artifact
from .lint import Issue
from .roles import covers

APPEARANCE_KEYS = {"base_artifact", "tenant", "origin", "targets", "timeouts", "watcher_triggers"}
BEHAVIOUR_KEYS = {"states", "transitions", "contract", "capability", "watchers", "provenance"}


def lint_overlay(base: Artifact, overlay: dict) -> list[Issue]:
    issues: list[Issue] = []

    if "needs" in overlay:
        widened = []
        for page in overlay["needs"].get("pages", []):
            if not covers(base.needs.pages, page):
                widened.append(page)
        for action in overlay["needs"].get("actions", []):
            if action not in base.needs.actions:
                widened.append(action)
        for secret in overlay["needs"].get("secrets", []):
            if secret not in base.needs.secrets:
                widened.append(secret)
        if widened:
            issues.append(Issue("overlay_widens_needs", "needs",
                                f"an overlay cannot add {widened!r}"))
        else:
            issues.append(Issue("overlay_changes_behaviour", "needs",
                                "needs belong to the artifact, not to an overlay"))

    for key in overlay:
        if key in BEHAVIOUR_KEYS:
            issues.append(Issue("overlay_changes_behaviour", key,
                                f"an overlay may not change {key!r}"))
        elif key not in APPEARANCE_KEYS and key != "needs":
            issues.append(Issue("overlay_unknown_key", key, "not an appearance key"))

    for name, rungs in overlay.get("targets", {}).items():
        if name not in base.targets:
            issues.append(Issue("overlay_unknown_target", f"targets.{name}",
                                "an overlay may only patch targets the artifact defines"))
            continue
        for rung in rungs:
            if "kind" not in rung:
                issues.append(Issue("overlay_bad_target", f"targets.{name}", "rung has no kind"))

    return issues


def apply_overlay(base: Artifact, overlay: dict) -> Artifact:
    """Merge an overlay onto an artifact. Caller must lint the overlay first."""
    data = base.model_dump(mode="python")
    for name, rungs in overlay.get("targets", {}).items():
        data["targets"][name] = rungs
    return Artifact.model_validate(data)
