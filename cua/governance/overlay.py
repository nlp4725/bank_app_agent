"""Tenant Overlays: may change how things look, never how they behave.

A patch that could add a step, alter the Contract or widen Needs would let a
cosmetic per-tenant file change what a reviewed capability does, so those keys
are rejected outright rather than merged. See CONTEXT.md, "Tenant Overlay".
"""

from ..domain.artifact import Artifact
from ..domain.issue import Issue
from .roles import covers

# `targets` is the only key that is applied. The other three say who the overlay is
# *for* — which Artifact, which Tenant, which instance — and are metadata a reviewer
# reads, not a patch: the address automation may use comes from the Tenant's Policy,
# which the institution owns, not from a file the provider ships.
#
# `timeouts` and `watcher_triggers` were listed here and merged by nothing, so an
# overlay could declare them, pass review and silently do nothing. A key that is not
# applied is now refused rather than ignored: see the cuts in REPORT.md §7.
APPEARANCE_KEYS = {"base_artifact", "tenant", "origin", "targets"}
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

    for name, target in overlay.get("targets", {}).items():
        if name not in base.targets:
            issues.append(Issue("overlay_unknown_target", f"targets.{name}",
                                "an overlay may only patch targets the artifact defines"))
            continue
        for rung in target.get("rungs", []):
            if "kind" not in rung:
                issues.append(Issue("overlay_bad_target", f"targets.{name}", "rung has no kind"))

    return issues


def apply_overlay(base: Artifact, overlay: dict) -> Artifact:
    """Merge an overlay onto an artifact. Caller must lint the overlay first."""
    data = base.model_dump(mode="python")
    for name, target in overlay.get("targets", {}).items():
        data["targets"][name] = target
    return Artifact.model_validate(data)
