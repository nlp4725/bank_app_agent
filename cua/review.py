"""Draft -> approved: the Reviewer's decisions, applied and then verified.

Nothing here guesses. A decisions file records what a person decided and why, the
decisions are applied mechanically, and approval is refused unless the result lints
clean and replays successfully on inputs the Discovery Run never saw.
"""

from copy import deepcopy

from .artifact import Artifact
from .lint import lint


def apply_decisions(draft: dict, decisions: dict) -> dict:
    """Apply a Reviewer's decisions to a draft. Every change is declared, not inferred."""
    art = deepcopy(draft)

    # 1. risk: every click arrived Consequential; the Reviewer marks the safe ones
    safe = set(decisions.get("safe_targets", []))
    for t in art["transitions"]:
        if t["action"]["target"] in safe:
            t["risk"] = "safe"

    # 2. interruptions: a transition the Reviewer judged to be an interstitial becomes
    #    a Watcher, and the transition is removed from the flow
    for item in decisions.get("interruptions", []):
        target = item["target"]
        removed = [t for t in art["transitions"] if t["action"]["target"] == target]
        art["transitions"] = [t for t in art["transitions"] if t["action"]["target"] != target]
        for t in removed:                       # stitch the flow back together
            for other in art["transitions"]:
                if other["to_state"] == t["from_state"]:
                    other["to_state"] = t["to_state"]
        art["states"] = [s for s in art["states"]
                         if any(t["from_state"] == s["id"] or t["to_state"] == s["id"]
                                for t in art["transitions"])]
        art["watchers"].append({
            "id": item["watcher_id"],
            "trigger": item["trigger"],
            "condition": "recoverable",
            "recovery": {"type": "click", "target": target},
            "budget": item.get("budget", 2),
            "provenance": item["provenance"],
        })

    # 3. watchers learnt from other Discovery Runs, or added by hand
    art["watchers"].extend(decisions.get("watchers", []))

    # 4. verification for each Consequential Action
    for item in decisions.get("verify_effects", []):
        for t in art["transitions"]:
            if t["action"]["target"] == item["target"]:
                t["verify_effect"] = item["verify_effect"]

    # 5. contract trimming: outcomes nothing can produce yet
    keep = set(decisions.get("keep_outcomes", []))
    if keep:
        art["contract"]["outcomes"] = [o for o in art["contract"]["outcomes"]
                                       if o["code"] in keep]

    # 6. needs, trimmed by the Reviewer
    for page in decisions.get("drop_pages", []):
        art["needs"]["pages"] = [p for p in art["needs"]["pages"] if p != page]

    art["capability"]["approvals"] = decisions.get("approvals", [])
    art["capability"]["version"] = decisions.get("version", art["capability"]["version"])
    return art


def approve(candidate: dict, *, verify, unattended: bool = True) -> tuple[Artifact | None, list]:
    """Approve only if it lints clean and a verify-replay passes on unseen inputs.

    PreAct's finding, one level up: a program that replays to its last step and still
    leaves the task undone must never enter the store.
    """
    art = Artifact.model_validate(candidate)
    issues = [i for i in lint(art, unattended=unattended) if i.code != "not_approved"]
    if issues:
        return None, issues
    result = verify(art)
    if result.status != "succeeded":
        return None, [f"verify-replay did not succeed: {result}"]
    approved = deepcopy(candidate)
    approved["capability"]["status"] = "approved"
    return Artifact.model_validate(approved), []
