"""The Operator's side of a handoff: a deliberately minimal console.

    python -m tools.operator                 # show the open intervention
    python -m tools.operator approve         # let the run perform the Consequential Action
    python -m tools.operator resume          # hand control back after an escalation
    python -m tools.operator abort           # stop the run

The run holds the browser open and polls for the decision file this writes. The
console is mocked on purpose (the brief allows it); the *seam* is real — same live
session, one holder at a time, and the human's actions recorded.
"""

import getpass
import json
import sys
from pathlib import Path

from cua.replay.handoff import open_requests


def open_intervention() -> Path | None:
    """The newest request a run is still waiting on. A finished run's request stays
    on disk as evidence, so the file existing is not enough: see waiting_request."""
    waiting = open_requests(Path("runs"))
    return waiting[0] if waiting else None


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    path = open_intervention()
    if path is None:
        print("no open intervention")
        return 0
    request = json.loads(path.read_text())
    if request.get("kind") == "approval":
        print(f"""
  APPROVAL      {request['run_id']}
  capability    {request['capability']}
  paused at     {request['state']}
  about to      act on {request['target']}  (found by {request['matched_by']})
  because       {request['reason']}
  the session   {request['url']}
  screenshot    {request['screenshot']}

  Nothing has been committed. Look at the browser if you want to, then:
      python -m tools.operator approve    |     python -m tools.operator abort
""")
    else:
        print(f"""
  INTERVENTION  {request['run_id']}
  capability    {request['capability']}
  stopped at    {request['state']}  ({request.get('watcher') or 'unknown state'})
  because       {request['reason']}
  the session   {request['url']}
  screenshot    {request['screenshot']}

  The browser is open and waiting. Do what is needed in it, then:
      python -m tools.operator resume     |     python -m tools.operator abort
""")
    if argv and argv[0] in ("approve", "resume", "abort"):
        decision = argv[0]
        (path.parent / "decision.json").write_text(json.dumps(
            {"decision": decision, "operator": f"operator:{getpass.getuser()}"}))
        print(f"  -> {decision}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
