"""Replay an approved capability. No model is involved.

    python -m tools.replay --list                        # the catalog: what can be replayed
    python -m tools.replay 12345                         # asks which capability, if more than one
    python -m tools.replay 12345 --capability member.read_savings_balance
    python -m tools.replay 12345 --headed                # watch the browser
    python -m tools.replay 12345 --headed --slowmo 2000  # slower, to follow along
    python -m tools.replay 99999                         # a business outcome
    python -m tools.replay 12345 lakeside --headed       # the second institution + overlay
    python -m tools.replay 12345 --headed --attended     # approve the commit at this terminal
    python -m tools.replay 44444 --headed --attended     # pauses for a human to take over

HEADED=1, ATTENDED=1 and CAPABILITY=… still work as environment variables.
"""

import argparse
import os

from cua.governance.store import artifacts
from tools.replay.run import run_replay

DEFAULT_CAPABILITY = os.environ.get("CAPABILITY")      # unset: choose from the catalog


def catalog() -> str:
    """Every artifact on disk, and whether a caller could invoke it."""
    rows = sorted(artifacts(), key=lambda a: (a.capability.id, a.capability.version))
    if not rows:
        return "  (no artifacts)"
    width = max(len(a.capability.id) for a in rows)
    return "\n".join(
        f"  {a.capability.id:{width}s}  {a.capability.version:8s} {a.capability.status:9s} "
        f"role {a.capability.role:16s} inputs {', '.join(a.contract.inputs)}"
        + ("" if a.capability.status == "approved" else "   (not replayable)")
        for a in rows)


def choose_capability(ask=input) -> str:
    """Which approved capability to run, when the caller did not say.

    One approved capability needs no question. Several do: a caller invokes a
    capability *by name*, so the name is never assumed on their behalf."""
    approved = sorted((a for a in artifacts() if a.capability.status == "approved"),
                      key=lambda a: a.capability.id)
    ids = sorted({a.capability.id for a in approved})
    if not ids:
        raise SystemExit("no approved capability to replay — approve one with tools.start first")
    if len(ids) == 1:
        return ids[0]
    print("\nWhich capability?\n")
    for n, cid in enumerate(ids, 1):
        art = next(a for a in approved if a.capability.id == cid)
        print(f"  {n}. {cid:30s} role {art.capability.role:16s} "
              f"inputs {', '.join(art.contract.inputs)}")
    while True:
        answer = ask("\n  number or name [1]: ").strip() or "1"
        if answer in ids:
            return answer
        if answer.isdigit() and 1 <= int(answer) <= len(ids):
            return ids[int(answer) - 1]
        print(f"  not one of the {len(ids)} above")


def parse_values(pairs):
    out = {}
    for pair in pairs or []:
        name, _, value = pair.partition("=")
        out[name.strip()] = value
    return out


def parse_args(argv=None):
    p = argparse.ArgumentParser(prog="python -m tools.replay", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("member", nargs="?", default="12345", help="member number (default 12345)")
    p.add_argument("tenant", nargs="?", default="bank_a", help="whose instance (default bank_a)")
    p.add_argument("--capability", "-c", default=DEFAULT_CAPABILITY,
                   help="capability id to replay (see --list); asked for when omitted and "
                        "more than one is approved")
    p.add_argument("--list", action="store_true", help="show the capability catalog and exit")
    p.add_argument("--headed", action="store_true", default=os.environ.get("HEADED") == "1",
                   help="watch the browser (or HEADED=1)")
    p.add_argument("--attended", action="store_true", default=os.environ.get("ATTENDED") == "1",
                   help="an Operator is on shift: approve each Consequential Action, take "
                        "over on escalation (or ATTENDED=1)")
    p.add_argument("--console", action="store_true",
                   help="attended, but answer in the Operator console (tools.operator) "
                        "rather than at this terminal")
    p.add_argument("--values", nargs="*", metavar="NAME=VALUE", help="other typed inputs")
    p.add_argument("--wait", type=float, default=float(os.environ.get("WAIT", "240")),
                   help="seconds to wait for an Operator when attended")
    p.add_argument("--slowmo", type=int, default=None, metavar="MS",
                   help="ms between steps when headed (default 900; try 2000 to follow along)")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    if args.list:
        print("\nCAPABILITIES — what a caller can invoke by name\n")
        print(catalog())
        print()
        return 0
    capability = args.capability or choose_capability()
    r = run_replay(capability, args.member, args.tenant, headed=args.headed,
                   attended=args.attended or args.console, values=parse_values(args.values),
                   wait_s=args.wait, slowmo_ms=args.slowmo, console=args.console)
    return 0 if r.status in ("succeeded", "business_outcome") else 1
