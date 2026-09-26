"""Reading a trail back: what a run that died mid-commit left behind."""

import json
from pathlib import Path


def unfinished(evidence_root) -> list[dict]:
    """Runs that died with a Consequential Action in flight.

    Each action is written down before it is performed and again after, and the line
    is flushed, so a run that stopped between the two leaves the pair unbalanced.
    On restart this is what turns "the process was killed mid-commit" into an answer
    — Outcome Unknown, do not retry — rather than silence. See docs/CONTEXT.md, the error
    table's last row.
    """
    found = []
    for trail in sorted(Path(evidence_root).glob("*/trail.jsonl")):
        in_flight, settled = None, False
        for line in trail.read_text().splitlines():
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if event["event"] == "about_to" and event.get("risk") == "consequential":
                in_flight = event
            elif event["event"] in ("done", "verification_check"):
                in_flight = None
            elif event["event"] == "result":
                settled = True
        if in_flight is not None and not settled:
            found.append({"run_id": in_flight["run_id"], "evidence": str(trail.parent),
                          "step": in_flight.get("step"),
                          "action": in_flight.get("action"),
                          "target": in_flight.get("target"),
                          "status": "outcome_unknown",
                          "guidance": "a consequential action was in flight when the "
                                      "run stopped; someone must check whether it "
                                      "took effect before it is tried again"})
    return found
