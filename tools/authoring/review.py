"""The second review, end to end: show the draft, ask the decisions, apply, verify,
save — and offer to watch the approved capability replay.

    python -m tools.start --review runs/disc_<id>           # redo it for an existing run
"""

import json
import os
from pathlib import Path

import yaml

from cua.authoring.recorder import record_from_run, watcher_from_run
from cua.authoring.review import apply_decisions, approve
from cua.domain.artifact import Artifact, merged
from cua.governance.profile import load_profile
from cua.governance.store import origin_for, refresh
from cua.replay.engine import RunContext, replay
from tools._cli import reset_or_exit, terminal_operator
from tools.authoring.interview import decide
from tools.authoring.walkthrough import show_draft
from tools.replay import run_replay

ARTIFACTS = Path("artifacts")
VERIFY_MEMBERS = ["12345", "54321"]      # normal members; verify on one discovery never saw
WATCH_PACE_MS = 2000                     # between steps when watching a replay after approval
PROBES = "probes.json"                   # beside a run: Outcome Code -> the run that probed it


def learnt_watchers(spec: dict, run_dir: str) -> dict:
    """Outcome Code -> Watcher, from the probe runs recorded beside this run.

    `probes.json` names, per Outcome Code, the run discovery made on inputs that should
    produce it; the inputs themselves stay in the Discovery Request file, not here."""
    probes = Path(run_dir) / PROBES
    if not probes.exists():
        return {}
    learnt = {}
    for code, probe_dir in json.loads(probes.read_text()).items():
        values = {**spec["example_values"], **spec.get("outcome_examples", {}).get(code, {})}
        watcher, why = watcher_from_run(probe_dir, values)
        if watcher is None or watcher["outcome"] != code:
            why = why if watcher is None else f"the run reported {watcher['outcome']}"
            print(f"  {code}: nothing learnt from {Path(probe_dir).name} — {why}")
            continue
        learnt[code] = watcher
    return learnt


def _watch(capability: str, member: str, tenant: str) -> None:
    run_replay(capability, member, tenant, headed=True, slowmo_ms=WATCH_PACE_MS, attended=True)


def review_artifact(spec: dict, run_dir: str, *, tenant: str = "bank_a", ask=input,
                    replay_fn=None, reviewer: str | None = None, watch_fn=None) -> int:
    """Show the draft, ask the decisions, apply, verify, save. Returns an exit code."""
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

    decisions = decide(draft, suggestions, spec, run_id, ask, reviewer,
                       learnt=learnt_watchers(spec, run_dir))
    ARTIFACTS.mkdir(exist_ok=True)
    dpath = ARTIFACTS / f"{stem}.decisions.yaml"
    dpath.write_text(f"# What the Reviewer decided about the draft compiled from {run_id}.\n"
                     f"# Applied mechanically by cua/authoring/review.py; nothing here is inferred.\n"
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
        reset_or_exit(origin)
        ready = Artifact.model_validate({**art.model_dump(), "capability":
                                         {**art.model_dump()["capability"], "status": "approved"}})
        # Attended: the Reviewer is the person present, and approves the commit here.
        return replay(merged(ready, profile), inputs,
                      RunContext(origin=origin, tenant=tenant, attended=True,
                                 operator=terminal_operator(ask)))

    print(f"\n  decisions saved to {dpath}\n  lint, then verify-replay on member {unseen} "
          f"(discovery never saw it) with no model; you approve its commit…")
    approved, problems = approve(candidate, verify=verify)
    if approved is None:
        print("\n  NOT APPROVED:")
        for pr in problems:
            print(f"    - {pr}")
        print(f"\n  fix {dpath} and rerun:  python -m tools.start --review {run_dir}")
        return 2
    out = ARTIFACTS / f"{stem}.{approved.capability.version}.yaml"
    out.write_text(yaml.safe_dump(approved.model_dump(exclude_none=True), sort_keys=False, width=100))
    refresh()           # the interview read the Store before this file existed
    print(f"\n  APPROVED -> {out}")
    # The walk-through shows the flow; the file is what was approved, and it also
    # carries the contract, needs and provenance the walk-through leaves out.
    if (ask("  show the approved file? [y/N]  ").strip().lower() or "n").startswith("y"):
        print()
        print("\n".join("    " + line for line in out.read_text().splitlines()))
    print(f"\n  it is now live — replay it with no model:\n"
          f"    python -m tools.replay {seen} --capability {spec['capability_id']}")
    if (ask(f"\n  Watch it replay now, in a visible browser, {WATCH_PACE_MS / 1000:g}s per step? "
            f"[Y/n]  ").strip().lower() or "y").startswith("y"):
        (watch_fn or _watch)(spec["capability_id"], seen, tenant)
    return 0
