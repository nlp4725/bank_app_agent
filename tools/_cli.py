"""What the command-line tools share and the package does not need: reading a
gitignored .env for the one key, printing a Discovery Result, and resetting the demo
app before a run."""

import json
import os
import urllib.error
import urllib.request
from pathlib import Path

DOTENV = Path(".env")


def load_dotenv(path: Path = DOTENV) -> list[str]:
    """`NAME=value` lines from a gitignored file into the environment, for the one tool
    that needs a key. A variable already set wins, so a shell export still overrides.
    Returns the names it set — never the values."""
    if not path.exists():
        return []
    loaded = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        name, value = name.strip(), value.strip().strip("'\"")
        if name and name not in os.environ:
            os.environ[name] = value
            loaded.append(name)
    return loaded


def report(result, actions: bool = True) -> None:
    print("\n=== result ===")
    print(result)
    print("outputs:", json.dumps(result.outputs, indent=2))
    print("evidence:", result.trace_dir)
    if result.draft:
        print(f"\n=== draft artifact compiled automatically ===\n  {result.draft}")
        print("  suggestions for the Reviewer:")
        for s in result.suggestions:
            print("   -", s[:104])
    if not actions:
        return
    print("\n=== actions recorded ===")
    for a in result.actions:
        rungs = " -> ".join(r["kind"] for r in a["target"]["rungs"]) or "(no rungs!)"
        print(f'  {a["turn"]:2d} {a["action"]:7s} {rungs:28s} '
              f'anchor={a["anchor"]!r} value={a.get("value")!r}')


def reset_or_exit(origin: str) -> None:
    """Restore the demo app's seed data — or say plainly that it is not running."""
    try:
        urllib.request.urlopen(f"{origin}/reset", timeout=5).read()
    except (urllib.error.URLError, OSError) as e:
        raise SystemExit(
            f"\nthe demo app is not answering at {origin} ({getattr(e, 'reason', e)}).\n"
            f"start it in another terminal, then run this again:\n"
            f"    python -m fake_bank.app                          # {origin}\n"
            f"    SKIN=bank2 PORT=5002 python -m fake_bank.app     # the second institution\n"
        ) from None


def terminal_operator(ask=input):
    """An Operator answering at this terminal: approvals are asked here, one question
    per Consequential Action; an escalation is left to the console (returns None, so
    the run waits on the decision file or on the blocking screen clearing)."""
    def operator(request, surface):
        if request.kind != "approval":
            return None
        answer = ask(f"\n  APPROVAL  {request.state}: the action on {request.target} commits "
                     f"(control found by {request.matched_by}). Approve? [Y/n]  ")
        return "abort" if answer.strip().lower().startswith("n") else "approve"
    return operator
