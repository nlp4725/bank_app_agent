"""Read a saved run: what the model was shown, what it asked for, what code did.

    python -m tools.inspect.show_run                     # the most recent run
    python -m tools.inspect.show_run runs/disc_4baf0086
    python -m tools.inspect.show_run runs/run_1a2b3c4d   # a replay run reads the same way
"""

import json
import sys
from pathlib import Path

WIDTH = 96


def latest() -> Path:
    runs = sorted(Path("runs").glob("*"), key=lambda p: p.stat().st_mtime, reverse=True)
    return next(p for p in runs if (p / "trail.jsonl").exists())


def main():
    run = Path(sys.argv[1]) if len(sys.argv) > 1 else latest()
    events = [json.loads(line) for line in (run / "trail.jsonl").read_text().splitlines()]
    print(f"\n{run}   {len(events)} events\n" + "=" * WIDTH)

    for e in events:
        kind = e["event"]
        if kind == "observed":
            print(f"\n── turn {e['turn']} ──────── {e['url']}")
            print(f"   screenshot: {e['screenshot']}")
            for line in e["controls"].splitlines():
                if line.strip():
                    print("   " + line[:WIDTH - 3])
                if line.startswith("visible text"):
                    break
        elif kind == "proposed":
            print(f"   MODEL  {e['tool']}   \"{e.get('reason', '')}\"")
        elif kind in ("policy_allow", "policy_deny"):
            mark = "allow" if kind.endswith("allow") else "DENY "
            print(f"   POLICY {mark}  {e.get('action')} on {e.get('path')}")
        elif kind == "acted":
            rungs = [r["kind"] for r in (e.get("target") or {}).get("rungs", [])]
            print(f"   CODE   acted, recorded {rungs}")
        elif kind == "about_to":
            print(f"   ACT    {e['action']} {e['target']} "
                  f"(matched_by={e.get('matched_by')}, risk={e.get('risk')})")
        elif kind == "watcher_matched":
            print(f"   WATCH  {e['watcher']} -> {e['condition']}")
        elif kind in ("checkpoint_missed", "reoriented", "recovered", "intervention_raised",
                      "operator_acted", "resumed", "verification_check", "overlay_applied"):
            print(f"   {kind.upper():<14} {json.dumps({k: v for k, v in e.items() if k not in ('ts', 'run_id', 'event')})[:WIDTH - 20]}")
        elif kind in ("ended", "result"):
            print("\n" + "=" * WIDTH)
            print("   " + json.dumps({k: v for k, v in e.items() if k not in ("ts", "run_id")}))


if __name__ == "__main__":
    main()
