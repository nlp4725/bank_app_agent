"""Turn a finished Discovery Run into a draft Artifact.

Mechanical, deterministic, and it makes no final judgement: where it must guess, it
attaches a suggestion for the Reviewer. The trace keeps the messy history; the
Artifact keeps the flow, decoupled from the model transcript.
"""

import json
import re
import shutil
from pathlib import Path

from .paths import ASSETS, ROOT

SLUG = re.compile(r"[^a-z0-9]+")


def slug(text: str) -> str:
    return SLUG.sub("_", (text or "").lower()).strip("_")[:28]


def target_name(action: dict) -> str:
    base = slug(action.get("anchor") or action.get("name") or action["action"])
    return f"t_{base or 'control'}"


def path_of(url: str) -> str:
    return "/" + url.split("//", 1)[-1].split("/", 1)[-1] if "//" in url else url


def page_pattern(path: str) -> str:
    """Concrete routes become patterns: /members/54321 -> /members/*"""
    parts = [p for p in path.split("/") if p]
    if len(parts) > 1:
        return "/" + parts[0] + "/*"
    return path or "/"


def keep_asset(crop: str, capability_id: str, assets_dir: Path | None) -> str | None:
    """Copy a record-time crop somewhere an Artifact may point at for years.

    A `picture` rung left pointing into `runs/` is the last rung of a Target's ladder
    resting on a directory that gets pruned. The Artifact owns its assets.

    None when the crop cannot be found: a rung naming a file that is not there is
    worse than no rung, because the ladder then claims a fallback it does not have.
    """
    root = Path(assets_dir) if assets_dir is not None else ASSETS / capability_id
    root.mkdir(parents=True, exist_ok=True)
    kept = root / Path(crop).name
    try:
        shutil.copy2(crop, kept)
    except OSError:
        return None
    try:
        return str(kept.resolve().relative_to(ROOT))   # portable: an Artifact travels
    except ValueError:
        return str(kept)


def record(actions: list[dict], contract: dict, example_values: dict, *,
           capability_id: str, vendor_app: str, role: str, version: str = "1.0.0",
           discovered_by: str = "", assets_dir=None) -> tuple[dict, list[str]]:
    """Returns (draft artifact, suggestions for the Reviewer)."""
    suggestions: list[str] = []
    targets: dict[str, dict] = {}
    states: list[dict] = []
    transitions: list[dict] = []
    # Keyed case-insensitively: a <select> shows "Savings" and carries the value
    # "savings", and the model points at what it can see. An exact-match map let that
    # difference freeze a discovery value into the flow as a literal.
    reverse = {str(v).casefold(): k for k, v in example_values.items()}

    # ── candidate interruptions ─────────────────────────────────────────────
    # A page visited once, entered and left by a single click, MIGHT be an
    # interstitial. It might equally be a confirmation screen, so nothing is
    # dropped: every action stays in the flow and the Reviewer decides.
    visits: dict[str, int] = {}
    for a in actions:
        visits[path_of(a["url_before"])] = visits.get(path_of(a["url_before"]), 0) + 1
    for a in actions:
        here = path_of(a["url_before"])
        if a["action"] == "click" and visits[here] == 1:
            suggestions.append(
                f"action {a['turn']} clicks {a.get('name') or a.get('anchor')!r} on {here}, a "
                f"page visited once. If that page was an interruption rather than part of the "
                f"flow, make it a Recoverable Watcher and delete this transition."
            )

    # ── one state per step ──────────────────────────────────────────────────
    # A State is the screen as it must be after one action, and every State carries
    # exactly one Checkpoint: what that action must have achieved. So every step is
    # verified before the next one acts (ADR 0007) — the same unit PreAct uses — and
    # the artifact reads as a straight line: at X (proved by …), do, now Y (proved by …).
    def page_slug(path):
        # From the pattern, never the concrete route: /members/54321 -> members_id,
        # so a discovery value cannot survive in an identifier.
        return slug(page_pattern(path).replace("/*", "_id").strip("/")) or "start"

    def control_slug(name):
        return name[2:] if name.startswith("t_") else name

    names: list[str] = []
    for a in actions:
        # Two controls can share an anchor — the member field and the search icon
        # beside it both read "Member number" — so a name collision is disambiguated
        # by role rather than silently pointing at the wrong control.
        name = target_name(a)
        if name in targets and targets[name] != a["target"]:
            name = f"{name}_{a['role']}"
        targets.setdefault(name, a["target"])
        names.append(name)
        if a.get("crop"):
            kept = keep_asset(a["crop"], capability_id, assets_dir)
            if kept is not None:
                targets[name].setdefault("rungs", []).append(
                    {"kind": "picture", "asset": kept})
            elif a["action"] == "click":          # only a click has a picture rung
                suggestions.append(
                    f"the record-time crop for {name} is missing ({a['crop']}), so it has "
                    f"no picture rung. Re-record, or accept a two-rung ladder.")

    if actions:
        states.append({"id": f"s1_{page_slug(path_of(actions[0]['url_before']))}",
                       "checkpoint": {"type": "element_present", "target": names[0]}})

    for i, a in enumerate(actions):
        name = names[i]
        here = states[-1]["id"]
        n = i + 2

        action = {"type": a["action"], "target": name}
        if a["action"] == "type":
            if a.get("value_ref"):
                action["value_ref"] = a["value_ref"]
            else:
                literal = str(a.get("value", ""))
                named = reverse.get(literal.casefold())
                action["value"] = f"{{{{{named}}}}}" if named else literal
                if not named and literal:
                    suggestions.append(
                        f"action {a['turn']} types the fixed value {literal!r}. "
                        f"Should it be an input?")
        elif a["action"] == "select":
            literal = str(a.get("value", ""))
            named = reverse.get(literal.casefold())
            action["value"] = f"{{{{{named}}}}}" if named else literal
            if not named and literal:
                suggestions.append(
                    f"action {a['turn']} selects the fixed option {literal!r}. "
                    f"Should it be an input?")
        elif a["action"] == "read":
            action["into"] = a["into"]

        # the State this step leads to, and the one Checkpoint that proves it
        after = path_of(a.get("url_after") or a["url_before"])
        if a["action"] in ("type", "select"):
            # the field now holds a value; non_empty rather than the value itself, so
            # a secret is never written into a predicate
            state = {"id": f"s{n}_{control_slug(name)}_entered",
                     "checkpoint": {"type": "field_value", "target": name, "non_empty": True}}
        elif a["action"] == "read":
            state = {"id": f"s{n}_{control_slug(name)}_read",
                     "checkpoint": {"type": "element_present", "target": name}}
        else:
            # a click: the screen it leads to is proved by the first control the next
            # step uses there. A final click has nothing after it to look for.
            nxt = names[i + 1] if i + 1 < len(names) else None
            state = {"id": f"s{n}_{page_slug(after)}",
                     "checkpoint": ({"type": "element_present", "target": nxt} if nxt else None)}
        states.append(state)

        transitions.append({
            "from_state": here, "to_state": state["id"], "action": action,
            # Every click arrives Consequential. Only a Reviewer may mark one Safe.
            "risk": "consequential" if a["action"] == "click" else "safe",
        })

    if states:
        states[-1]["terminal"] = "succeeded"

    # ── needs: only what the run actually used ──────────────────────────────
    needs = {
        "pages": sorted({page_pattern(path_of(a["url_before"])) for a in actions}),
        "actions": sorted({a["action"] for a in actions}),
        "secrets": sorted({a["value_ref"] for a in actions if a.get("value_ref")}),
    }

    artifact = {
        "schema_version": 1,
        "capability": {"id": capability_id, "version": version, "vendor_app": vendor_app,
                       "role": role, "status": "draft", "approvals": []},
        "contract": contract,
        "needs": needs,
        "targets": targets,
        "states": states,
        "transitions": transitions,
        "watchers": [],
        "provenance": {"discovered_by": discovered_by, "contract_by": "reviewer",
                       "example_values": {k: str(v) for k, v in example_values.items()}},
    }
    suggestions.append("every click is marked Consequential: mark the safe ones Safe.")
    suggestions.append("no Watchers yet: run discovery on the not-found member to learn one.")
    return artifact, suggestions


def record_from_run(run_dir: str, contract: dict, example_values: dict, **kwargs):
    """Compile a saved run. Crops are found beside the run, wherever it now lives.

    `actions.json` records each crop by the path it had when it was written. A run
    that has since been copied — into `evidence/`, or onto another machine — still
    has its crops in its own `screens/` directory, so look there before giving up.
    """
    run = Path(run_dir)
    actions = json.loads((run / "actions.json").read_text())
    for action in actions:
        crop = action.get("crop")
        if crop and not Path(crop).exists():
            beside = run / "screens" / Path(crop).name
            action["crop"] = str(beside) if beside.exists() else None
    return record(actions, contract, example_values,
                  discovered_by=run.name, **kwargs)
