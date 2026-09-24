"""What the command-line tools share and the package does not need: reading a
gitignored .env for the one key, and printing a Discovery Result."""

import json
import os
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
