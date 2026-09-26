"""The Reviewer's answers, as a decisions file.

The Recorder decides nothing (docs/CONTEXT.md). What it could not decide is asked here, one
question each, and the answers are written to a decisions file before they are
applied — so the review is a file, and `tools.start --review runs/<id>` can redo it.
`cua/authoring/review.py` applies the file mechanically; nothing here is inferred.
"""

import re

from cua.governance.store import artifacts
from tools.authoring.walkthrough import target_words

APPROVER = re.compile(r"^[a-z_]+:[A-Za-z0-9_.-]+$")     # role:name, e.g. reviewer:nasi


def known_watchers(vendor_app: str) -> dict[str, tuple[str, dict]]:
    """Outcome code -> (capability that has it, its watcher), from the store."""
    out = {}
    for art in artifacts():
        if art.capability.vendor_app != vendor_app:
            continue
        for w in art.watchers:
            if w.outcome and w.outcome not in out:
                out[w.outcome] = (art.capability.id, w.model_dump(exclude_none=True))
    return out


def decide(draft: dict, suggestions: list[str], spec: dict, run_id: str, ask=input,
           reviewer: str = "reviewer") -> dict:
    """The Reviewer's answers, as a decisions file cua/authoring/review.py applies mechanically."""
    decisions = {"version": draft["capability"]["version"], "approvals": [],
                 "safe_targets": [], "interruptions": [], "watchers": [], "keep_outcomes": []}

    # 1. risk: every click arrived Consequential. The risk is the action's — doing
    #    this, here — so the question names the step and the action; the decisions
    #    file records the answer by the target it acts on, which is how it is applied.
    print()
    for n, t in enumerate(draft["transitions"], 1):
        if t["risk"] != "consequential":
            continue
        hint = t.get("risk_suggestion")
        default = "n" if hint and re.search(r"creat|commit|submit|open", hint, re.I) else "y"
        target = t["action"]["target"]
        q = (f"  STEP {n}  {t['action']['type']} {target_words(draft, target).split('   (')[0]}"
             f"   (target {target}, {t['from_state']} -> {t['to_state']})\n"
             + (f"          the model's note: {hint}\n" if hint else "")
             + f"          is this action safe — it only navigates, commits nothing? "
             f"[{'Y/n' if default == 'y' else 'y/N'}]  ")
        if (ask(q).strip().lower() or default).startswith("y"):
            decisions["safe_targets"].append(target)

    # 2. interruptions the Recorder noticed
    for s in suggestions:
        m = re.search(r"clicks '([^']+)' on (\S+), a page visited once", s)
        if not m:
            continue
        label, page = m.group(1), m.group(2).rstrip(",")
        t = _transition_clicking(draft, label)
        if t is None:
            continue
        if (ask(f"  the click on '{label}' ({page}) happened on a screen seen once: an "
                f"interruption, not part of the flow? [y/N]  ").strip().lower() or "n").startswith("y"):
            text = ask("    text on that screen that identifies it: ").strip() or label
            decisions["interruptions"].append({
                "target": t["action"]["target"], "watcher_id": f"w_{_slug(text)}",
                "trigger": {"type": "text_present", "value": text}, "budget": 2,
                "provenance": run_id})

    # 3. a watcher for every declared outcome, or the outcome goes
    have = {w["outcome"] for w in draft["watchers"] if w.get("outcome")}
    known = known_watchers(spec["vendor_app"])
    for o in draft["contract"]["outcomes"]:
        code = o["code"]
        if code in have:
            decisions["keep_outcomes"].append(code)
            continue
        if code in known:
            owner, w = known[code]
            if (ask(f"  {code}: reuse watcher {w['id']} — text {w['trigger'].get('value')!r} "
                    f"(from {owner})? [Y/n]  ").strip().lower() or "y").startswith("y"):
                decisions["watchers"].append({**w, "provenance": f"reuse:{owner}"})
                decisions["keep_outcomes"].append(code)
                continue
        answer = ask(f"  {code}: no watcher can recognise it yet. "
                     f"[t]ext on screen that means it, or [d]rop it from the contract  ").strip()
        if answer.lower().startswith("t") or (answer and not answer.lower().startswith("d")):
            text = answer[1:].strip() if answer.lower().startswith("t") else answer
            text = text or ask("    the text: ").strip()
            while text and len(text) < 6:
                print(f"    {text!r} is too short to identify a screen; quote the message the app shows")
                text = ask("    the text (or Enter to drop the outcome): ").strip()
            if text:
                decisions["watchers"].append({
                    "id": f"w_{_slug(text)}", "trigger": {"type": "text_present", "value": text},
                    "condition": "business_outcome", "outcome": code, "provenance": reviewer})
                decisions["keep_outcomes"].append(code)
                continue
        print(f"    {code} dropped from the contract")

    # 4. a Verification Check for every step that still commits: how to see the effect
    #    without clicking again. Without one the step can never run unattended.
    still = [t for t in draft["transitions"]
             if t["risk"] == "consequential" and t["action"]["target"] not in decisions["safe_targets"]]
    decisions["verify_effects"] = []
    inputs = list(draft["contract"]["inputs"])
    for t in still:
        target = t["action"]["target"]
        print(f"  the {t['action']['type']} on {target} commits. To check its effect without "
              f"doing it again:")
        goto = ask(f"    page to open afterwards [/members/{{{{{inputs[0] if inputs else 'id'}}}}}]: ").strip() \
               or (f"/members/{{{{{inputs[0]}}}}}" if inputs else "/")
        text = ask("    text on that page that proves it happened (may use {{input}}): ").strip()
        if text:
            decisions["verify_effects"].append({
                "target": target,
                "verify_effect": {"goto": goto, "predicate": {"type": "text_present", "value": text}}})
        else:
            print(f"    no check given: {target} will be refused for unattended replay")

    # 5. who approves — two names when anything still commits
    decisions["approvals"] = [ask_approver(ask, f"  approve as [{reviewer}]: ", reviewer)]
    if still:
        print(f"  {len(still)} step(s) still commit: a second approval is required")
        second = ask_approver(ask, "  second approver: ", None)
        if second:
            decisions["approvals"].append(second)
    return decisions


def ask_approver(ask, prompt: str, default: str | None) -> str | None:
    """A name in the form role:name. 'yes' is an answer to a different question."""
    while True:
        answer = ask(prompt).strip() or default
        if answer is None or APPROVER.match(answer):
            return answer
        print(f"    an approver is written role:name, e.g. reviewer:{answer.lower()}")


def _transition_clicking(draft: dict, label: str):
    """The click whose Target is found by this label — by accessible name or caption."""
    for t in draft["transitions"]:
        if t["action"]["type"] != "click":
            continue
        for r in draft["targets"][t["action"]["target"]]["rungs"]:
            if r.get("name") == label or r.get("anchor") == label:
                return t
    return None


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:32]
