"""The Operator's side of a handoff: a deliberately minimal console.

    python -m tools.operator                 # show the open intervention
    python -m tools.operator resume          # hand control back
    python -m tools.operator abort           # stop the run

The run holds the browser open and polls for the decision file this writes. The
console is mocked on purpose (the brief allows it); the *seam* is real — same live
session, one holder at a time, and the human's actions recorded.
"""

import json
import sys
from pathlib import Path


def open_intervention() -> Path | None:
    candidates = sorted(Path("runs").glob("run_*/intervention.json"),
                        key=lambda p: p.stat().st_mtime, reverse=True)
    for path in candidates:
        if not (path.parent / "decision.json").exists():
            return path
    return None


def main():
    path = open_intervention()
    if path is None:
        print("no open intervention")
        return
    request = json.loads(path.read_text())
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
    if len(sys.argv) > 1 and sys.argv[1] in ("resume", "abort"):
        decision = sys.argv[1]
        (path.parent / "decision.json").write_text(json.dumps(
            {"decision": decision, "operator": f"operator:{__import__('getpass').getuser()}"}))
        print(f"  -> {decision}")


if __name__ == "__main__":
    main()
