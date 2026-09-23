"""Start with a goal. The interactive front door to discovery.

    python -m tools.start

    What do you want to do today?: look up a member and read their savings balance

      capability  member.read_savings_balance
      role        balance_reader — View member information and balances.
      inputs      member_number   string  ^[0-9]{5}$  (sensitive)

      returns     succeeded         -> outputs:
                                       savings_balance    money
                  business_outcome  -> one of:
                                       MEMBER_NOT_FOUND   resolver: member
                                       NOT_AUTHORIZED     resolver: institution_staff
                                       NO_SAVINGS_ACCOUNT resolver: member
                  failed | refused | aborted | outcome_unknown  (engine; not reviewed here)

    Approve this contract? [Y/n/e]  y
    member_number [54321]: 12345
    Watch the browser? [Y/n]  y

Two review points. This tool reviews the *Contract* — the interface — before any run;
approving it saves `contracts/<name>.yaml`, `e` saves it for editing, `n` saves nothing.
The *Artifact* — the plan of steps — cannot be reviewed until discovery has produced a
draft; that is `tools.record` and `tools.review`, afterwards.
"""

import argparse
import re
import sys
from pathlib import Path

import yaml

from cua.discovery import ProposalError, discover, propose_contract
from cua.roles import get_role
from tools.discover import load_dotenv, report, request_from_spec

VENDOR_APP = "demo-core-servicing"
CONTRACTS = Path("contracts")


def known_outcomes(vendor_app: str) -> list[dict]:
    """Outcome codes the other Discovery Requests on this app already use, by code."""
    seen = {}
    for path in sorted(CONTRACTS.glob("*.yaml")):
        spec = yaml.safe_load(path.read_text()) or {}
        if spec.get("vendor_app") != vendor_app:
            continue
        for o in spec.get("contract", {}).get("outcomes", []):
            seen.setdefault(o["code"], o)
    return list(seen.values())


def show(spec: dict) -> str:
    role = get_role(spec["vendor_app"], spec["role"])
    c = spec["contract"]
    lines = [f"  capability  {spec['capability_id']}",
             f"  role        {spec['role']} — {role.get('intent', '')}"
             + (f"\n              ({spec['why_this_role']})" if spec.get("why_this_role") else ""),
             f"  goal        {spec['goal']}"]
    for name, i in c["inputs"].items():
        rule = i.get("pattern") or (f"one of {', '.join(i['values'])}" if i.get("values") else "")
        rule = rule or (f"≤ {i['max_length']} chars" if i.get("max_length") else "")
        lines.append(f"  input       {name:18s} {i['type']:7s} {rule}"
                     + ("  (sensitive)" if i.get("sensitive") else ""))
    lines.append("")
    lines.append("  returns     succeeded         -> outputs:")
    for name, o in c["outputs"].items():
        lines.append(f"                                   {name:18s} {o['type']}"
                     + ("  (sensitive)" if o.get("sensitive") else ""))
    lines.append("              business_outcome  -> one of:")
    for o in c["outcomes"]:
        lines.append(f"                                   {o['code']:18s} resolver: {o['resolver']}")
    if not c["outcomes"]:
        lines.append("                                   (none proposed)")
    lines.append("              failed | refused | aborted | outcome_unknown  (engine; not reviewed here)")
    return "\n".join(lines)


def check(spec_in: dict, value: str) -> str | None:
    """Why this value is not acceptable for this input, or None."""
    if spec_in.get("pattern") and not re.fullmatch(spec_in["pattern"], value):
        return f"must match {spec_in['pattern']}"
    if spec_in.get("values") and value not in spec_in["values"]:
        return f"must be one of {', '.join(spec_in['values'])}"
    if spec_in.get("max_length") and len(value) > spec_in["max_length"]:
        return f"at most {spec_in['max_length']} characters"
    return None


def ask_values(spec: dict, ask=input) -> dict:
    values = {}
    for name, i in spec["contract"]["inputs"].items():
        default = spec.get("example_values", {}).get(name, "")
        while True:
            raw = ask(f"{name} [{default}]: " if default else f"{name}: ").strip() or default
            problem = check(i, raw)
            if problem is None and raw:
                values[name] = raw
                break
            print(f"  {name}: {problem or 'a value is needed'}")
    return values


def save(spec: dict) -> Path:
    CONTRACTS.mkdir(exist_ok=True)
    stem = spec["capability_id"].split(".")[-1]
    path = CONTRACTS / f"{stem}.yaml"
    out = {k: spec[k] for k in ("capability_id", "vendor_app", "role", "goal",
                                "example_values", "contract")}
    path.write_text("# Proposed by the model from a goal typed in words; confirmed by a "
                    "Reviewer in tools.start.\n" + yaml.safe_dump(out, sort_keys=False, width=100))
    return path


def run(goal: str | None = None, *, tenant: str = "bank_a", ask=input,
        propose=propose_contract, discover_fn=discover, headed: bool | None = None,
        slowmo: int = 400, replay_fn=None) -> int:
    """The conversation. Returns a shell exit code."""
    goal = goal or ask("What do you want to do today?: ").strip()
    if not goal:
        print("Nothing to do.")
        return 1

    # A model call takes a few seconds; say so on one line, then erase it.
    print("  …", end="", flush=True)
    try:
        spec = propose(goal, VENDOR_APP, known_outcomes=known_outcomes(VENDOR_APP))
    except ProposalError as e:
        print(f"\r  could not propose a capability: {e}")
        return 1
    print("\r   \r", end="")
    print()
    print(show(spec))
    print()

    answer = (ask("Approve this contract? [Y/n/e]  ").strip().lower() or "y")
    if answer.startswith("e"):
        path = save(spec)
        print(f"\n  saved to {path} — edit it, then:\n"
              f"  python -m tools.discover --contract {path} --headed")
        return 0
    if not answer.startswith("y"):
        print("\n  not approved; nothing saved, nothing ran.")
        return 0

    values = ask_values(spec, ask)
    spec["example_values"] = values
    path = save(spec)
    if headed is None:
        headed = (ask("Watch the browser? [Y/n]  ").strip().lower() or "y").startswith("y")

    request = request_from_spec(spec, values, tenant=tenant, headed=headed,
                                slowmo=slowmo if headed else 0)
    print(f"\n  saved to {path}\n  starting discovery for {spec['capability_id']} "
          f"at {tenant} ({request.origin})\n")
    result = discover_fn(request)
    report(result, actions=not result.draft)      # the draft shows the steps in full
    if result.draft:
        return review_artifact(spec, result.trace_dir, tenant=tenant, ask=ask, replay_fn=replay_fn)
    return 0 if result.ending in ("goal_reached", "report_outcome") else 2


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m tools.start", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--goal", help="skip the first question")
    p.add_argument("--tenant", default="bank_a")
    p.add_argument("--headless", action="store_true", help="never ask; no browser window")
    p.add_argument("--review", metavar="RUN_DIR",
                   help="skip discovery: review the draft of an existing run, e.g. runs/disc_12e097f2")
    args = p.parse_args(argv)
    load_dotenv()
    try:
        if args.review:
            return review_artifact(spec_for_run(args.review), args.review, tenant=args.tenant)
        return run(args.goal, tenant=args.tenant, headed=False if args.headless else None)
    except (KeyboardInterrupt, EOFError):
        print("\nstopped.")
        return 130



# ── the second review: the Artifact, right after the run ─────────────────────
#
# The Recorder decides nothing (CONTEXT.md). What it could not decide is asked here,
# one question each, and the answers are written to a decisions file before they are
# applied — so the review is a file, and `tools.start --review runs/<id>` can redo it.

import re as _re

ARTIFACTS = Path("artifacts")
VERIFY_MEMBERS = ["12345", "54321"]      # normal members; verify on one discovery never saw


def known_watchers(vendor_app: str) -> dict[str, tuple[str, dict]]:
    """Outcome code -> (capability that has it, its watcher), from the store."""
    from cua.store import artifacts
    out = {}
    for art in artifacts():
        if art.capability.vendor_app != vendor_app:
            continue
        for w in art.watchers:
            if w.outcome and w.outcome not in out:
                out[w.outcome] = (art.capability.id, w.model_dump(exclude_none=True))
    return out


def _target_words(draft: dict, name: str) -> str:
    """A Target's ladder in words: how the control is found, rung by rung."""
    tg = draft["targets"][name]
    words = []
    for r in tg["rungs"]:
        if r["kind"] == "role_name":
            words.append(f"the {r['role']} named \"{r['name']}\"")
        elif r["kind"] == "label_anchor":
            what = r.get("role") or "control"
            rel = {"right_of": "right of", "below": "below", "nearest": "nearest"}.get(
                r.get("relation", "nearest"), r.get("relation"))
            words.append(f"the {what} {rel} the caption \"{r['anchor']}\"")
        else:
            words.append("its picture")
    frame = f", inside frame {tg['frame']['url_contains']}" if tg.get("frame") else ""
    return f"{words[0]}{frame}" + (f"   (fallback: {', '.join(words[1:])})" if len(words) > 1 else "")


def _checkpoint_words(draft: dict, state_id: str) -> str:
    st = next((s for s in draft["states"] if s["id"] == state_id), None)
    cp = (st or {}).get("checkpoint")
    if not cp:
        return "no checkpoint (terminal)" if st and st.get("terminal") else "no checkpoint"
    if cp["type"] == "element_present":
        return f"target {cp['target']} is on screen"
    if cp["type"] == "text_present":
        return f"the text \"{cp['value']}\" is on screen"
    if cp["type"] == "url_matches":
        return f"the address matches {cp['pattern']}"
    if cp["type"] == "field_value":
        return (f"field {cp['target']} holds a value" if cp.get("non_empty")
                else f"field {cp['target']} reads {cp.get('equals')!r}")
    return f"{cp['type']} holds"


def show_draft(draft: dict, suggestions: list[str]) -> str:
    """The draft as a walk-through: one block per step, everything about that step in
    it — where we are and how we know (checkpoint), what we do, on which target and how
    it is found, where we land."""
    c = draft["capability"]
    lines = [f"  {c['id']} {c['version']}   role {c['role']}   status {c['status']}",
             f"  {len(draft['states'])} states, {len(draft['transitions'])} steps, "
             f"{len(draft['watchers'])} watchers"]
    here = None
    for n, t in enumerate(draft["transitions"], 1):
        a = t["action"]
        lines.append("")
        at = f"  STEP {n:<2d}  at {t['from_state']}"
        if t["from_state"] != here:
            at += f"      checkpoint: {_checkpoint_words(draft, t['from_state'])}"
        lines.append(at)
        verb = {"type": "type", "click": "click", "select": "select", "read": "read"}[a["type"]]
        if a["type"] == "type":
            value = f"<secret {a['value_ref']}>" if a.get("value_ref") else repr(a.get("value"))
            lines.append(f"           {verb:6s} {value}")
            lines.append(f"           into   target {a['target']}  =  {_target_words(draft, a['target'])}")
        elif a["type"] == "select":
            lines.append(f"           {verb:6s} {a.get('value')!r}")
            lines.append(f"           in     target {a['target']}  =  {_target_words(draft, a['target'])}")
        elif a["type"] == "read":
            lines.append(f"           {verb:6s} target {a['target']}  =  {_target_words(draft, a['target'])}")
            lines.append(f"           into   output {a['into']}")
        else:
            lines.append(f"           {verb:6s} target {a['target']}  =  {_target_words(draft, a['target'])}")
        if t["to_state"] != t["from_state"]:
            lines.append(f"           then   {t['to_state']}      checkpoint: {_checkpoint_words(draft, t['to_state'])}")
        else:
            lines.append(f"           then   still {t['to_state']}")
        st = next((s for s in draft["states"] if s["id"] == t["to_state"]), {})
        if st.get("terminal") and n == len(draft["transitions"]):
            lines.append(f"           done   {t['to_state']} is terminal: SUCCEEDED")
        if t["risk"] == "consequential":
            lines.append(f"           risk   CONSEQUENTIAL  <- you decide: does this click commit anything?")
        if t.get("verify_effect"):
            lines.append(f"           verify open {t['verify_effect']['goto']}, "
                         f"expect the text {t['verify_effect']['predicate'].get('value')!r}")
        here = t["to_state"]

    lines.append("")
    lines.append("  WATCHERS   if a checkpoint fails, which screen is it?")
    if draft["watchers"]:
        for w in draft["watchers"]:
            tail = (f"outcome {w['outcome']}" if w.get("outcome")
                    else f"click {w['recovery']['target']}" if w.get("recovery") else "")
            lines.append(f"           {w['id']:22s} text \"{w['trigger'].get('value')}\"  ->  {w['condition']}  {tail}")
    else:
        lines.append("           none yet  <- the next questions add them")

    if suggestions:
        lines.append("")
        lines.append("  the Recorder could not decide:")
        lines += [f"    - {s}" for s in suggestions]
    return "\n".join(lines)


def decide(draft: dict, suggestions: list[str], spec: dict, run_id: str, ask=input,
           reviewer: str = "reviewer") -> dict:
    """The Reviewer's answers, as a decisions file cua/review.py applies mechanically."""
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
        default = "n" if hint and _re.search(r"creat|commit|submit|open", hint, _re.I) else "y"
        target = t["action"]["target"]
        q = (f"  STEP {n}  {t['action']['type']} {_target_words(draft, target).split('   (')[0]}"
             f"   (target {target}, {t['from_state']} -> {t['to_state']})\n"
             + (f"          the model's note: {hint}\n" if hint else "")
             + f"          is this action safe — it only navigates, commits nothing? "
             f"[{'Y/n' if default == 'y' else 'y/N'}]  ")
        if (ask(q).strip().lower() or default).startswith("y"):
            decisions["safe_targets"].append(target)

    # 2. interruptions the Recorder noticed
    for s in suggestions:
        m = _re.search(r"clicks '([^']+)' on (\S+), a page visited once", s)
        if not m:
            continue
        label, page = m.group(1), m.group(2).rstrip(",")
        t = _transition_clicking(draft, label)
        if t is None:
            continue
        if (ask(f"  the click on '{label}' ({page}) happened on a screen seen once: an "
                f"interruption, not part of the flow? [y/N]  ").strip().lower() or "n").startswith("y"):
            text = ask(f"    text on that screen that identifies it: ").strip() or label
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
        text = ask(f"    text on that page that proves it happened (may use {{{{input}}}}): ").strip()
        if text:
            decisions["verify_effects"].append({
                "target": target,
                "verify_effect": {"goto": goto, "predicate": {"type": "text_present", "value": text}}})
        else:
            print(f"    no check given: {target} will be refused for unattended replay")

    # 5. who approves — two names when anything still commits
    first = ask(f"  approve as [{reviewer}]: ").strip() or reviewer
    decisions["approvals"] = [first]
    if still:
        print(f"  {len(still)} step(s) still commit: a second approval is required")
        second = ask("  second approver: ").strip()
        if second:
            decisions["approvals"].append(second)
    return decisions


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
    return _re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:32]


def review_artifact(spec: dict, run_dir: str, *, tenant: str = "bank_a", ask=input,
                    replay_fn=None, reviewer: str | None = None) -> int:
    """Show the draft, ask the decisions, apply, verify, save. Returns an exit code."""
    import os
    import urllib.request
    from cua.artifact import Artifact, merged
    from cua.engine import RunContext, replay
    from cua.profile import load_profile
    from cua.recorder import record_from_run
    from cua.review import apply_decisions, approve
    from cua.store import origin_for

    reviewer = reviewer or f"reviewer:{os.environ.get('USER', 'reviewer')}"
    run_id = Path(run_dir).name
    draft, suggestions = record_from_run(
        run_dir, spec["contract"], spec["example_values"],
        capability_id=spec["capability_id"], vendor_app=spec["vendor_app"], role=spec["role"])
    stem = spec["capability_id"].split(".")[-1]

    print()
    print(show_draft(draft, suggestions))
    answer = (ask("\nReview this artifact now? [Y/n]  ").strip().lower() or "y")
    if not answer.startswith("y"):
        print(f"  draft left at {run_dir}/draft.yaml — review later with:\n"
              f"  python -m tools.start --review {run_dir}")
        return 0

    decisions = decide(draft, suggestions, spec, run_id, ask, reviewer)
    ARTIFACTS.mkdir(exist_ok=True)
    dpath = ARTIFACTS / f"{stem}.decisions.yaml"
    dpath.write_text(f"# What the Reviewer decided about the draft compiled from {run_id}.\n"
                     f"# Applied mechanically by cua/review.py; nothing here is inferred.\n"
                     + yaml.safe_dump(decisions, sort_keys=False, width=100))
    candidate = apply_decisions(draft, decisions)

    origin = origin_for(tenant, spec["vendor_app"])
    profile = load_profile(spec["vendor_app"])
    seen = spec["example_values"].get("member_number")
    unseen = next((m for m in VERIFY_MEMBERS if m != seen), VERIFY_MEMBERS[0])
    inputs = {**spec["example_values"], "member_number": unseen}

    def verify(art: Artifact):
        if replay_fn is not None:
            return replay_fn(art, inputs)
        urllib.request.urlopen(f"{origin}/reset", timeout=5).read()
        ready = Artifact.model_validate({**art.model_dump(), "capability":
                                         {**art.model_dump()["capability"], "status": "approved"}})
        return replay(merged(ready, profile), inputs, RunContext(origin=origin, tenant=tenant))

    print(f"\n  decisions saved to {dpath}\n  lint, then verify-replay on member {unseen} "
          f"(discovery never saw it) with no model…")
    approved, problems = approve(candidate, verify=verify)
    if approved is None:
        print("\n  NOT APPROVED:")
        for pr in problems:
            print(f"    - {pr}")
        print(f"\n  fix {dpath} and rerun:  python -m tools.start --review {run_dir}")
        return 2
    out = ARTIFACTS / f"{stem}.{approved.capability.version}.yaml"
    out.write_text(yaml.safe_dump(approved.model_dump(exclude_none=True), sort_keys=False, width=100))
    print(f"\n  APPROVED -> {out}\n"
          f"  it is now live: CAPABILITY={spec['capability_id']} python -m tools.replay {seen}")
    return 0


def spec_for_run(run_dir: str) -> dict:
    """The Discovery Request a run was made from, by its draft's capability id."""
    draft = yaml.safe_load((Path(run_dir) / "draft.yaml").read_text())
    stem = draft["capability"]["id"].split(".")[-1]
    path = CONTRACTS / f"{stem}.yaml"
    if not path.exists():
        raise SystemExit(f"no {path} for {draft['capability']['id']}")
    return yaml.safe_load(path.read_text())


if __name__ == "__main__":
    sys.exit(main())
