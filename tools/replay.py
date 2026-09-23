"""Replay an approved capability. No model is involved.

    python -m tools.replay --list                        # the catalog: what can be replayed
    python -m tools.replay 12345                         # the default capability, member 12345
    python -m tools.replay 12345 --capability member.read_savings_balance
    python -m tools.replay 12345 --headed                # watch the browser
    python -m tools.replay 99999                         # a business outcome
    python -m tools.replay 12345 lakeside --headed       # the second institution + overlay
    python -m tools.replay 44444 --headed --attended     # pauses for a human to take over

Which artifact runs is the Capability Store's answer (cua/store.py): the highest
*approved* version of the capability id — a draft never replays. HEADED=1, ATTENDED=1
and CAPABILITY=… still work as environment variables.
"""

import argparse
import os
import sys
import time
import urllib.error
import urllib.request

from cua.engine import RunContext, replay
from cua.narration import from_env
from cua.store import artifacts, load_capability, origin_for, overlay_for

DEFAULT_CAPABILITY = os.environ.get("CAPABILITY", "member.open_sub_account")
VENDOR_APP = "demo-core-servicing"
DEMO_VALUES = {"account_type": "savings", "nickname": "Live demo"}   # for inputs the caller did not give


def describe(art):
    """The header every run prints: what is about to execute, and what the caller sees."""
    print(f"\ncapability   {art.capability.id}@{art.capability.version}  "
          f"({art.capability.status}, role {art.capability.role})")
    print(f"approved by  {', '.join(art.capability.approvals)}")
    print("\nCONTRACT — all the caller sees")
    print("  inputs   " + ", ".join(
        f"{n}: {s.type}{' ' + s.pattern if s.pattern else ''}"
        for n, s in art.contract.inputs.items()))
    print("  outputs  " + ", ".join(f"{n}: {s.type}" for n, s in art.contract.outputs.items()))
    print("  outcomes " + ", ".join(f"{o.code} (resolver: {o.resolver})"
                                    for o in art.contract.outcomes))
    print(f"\nFLOW — {len(art.states)} states, {len(art.transitions)} transitions, "
          f"{len(art.watchers)} watchers, "
          f"{sum(1 for t in art.transitions if t.risk == 'consequential')} consequential")


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


def inputs_for(art, member: str, given: dict | None = None) -> dict:
    """The typed inputs this contract needs: the member, what the caller gave, and demo
    values for the rest — never an input the contract does not declare."""
    values = {"member_number": member, **DEMO_VALUES, **(given or {})}
    return {name: values[name] for name in art.contract.inputs if name in values}


def run_replay(capability: str, member: str, tenant: str = "bank_a", *, headed: bool = False,
               attended: bool = False, values: dict | None = None, wait_s: float = 240.0):
    """One replay, narrated to the console. Returns the RunResult."""
    # One question to the Capability Store: which Artifact is live, where this Tenant
    # runs it, and what it looks like there.
    art = load_capability(capability)
    origin = origin_for(tenant, VENDOR_APP)
    overlay = overlay_for(tenant)

    describe(art)
    if attended:
        print("\nATTENDED: if this run escalates, it will pause and wait for an Operator.")
        print("  1. do what is needed in the browser it leaves open")
        print("  2. python -m tools.operator            (see the request)")
        print("  3. python -m tools.operator resume     (or: abort)")
    print(f"\nreplaying for member {member} at {tenant} ({origin}) — no model in the loop\n")

    reset_or_exit(origin)
    started = time.time()
    env = dict(os.environ, VERBOSE="1", HEADED="1" if headed else os.environ.get("HEADED", "0"))
    r = replay(art, inputs_for(art, member, values),
               RunContext(origin=origin, tenant=tenant, overlay=overlay, headless=not headed,
                          narrator=from_env(env), attended=attended, operator_timeout_s=wait_s))
    print(f"\nRESULT  {r}")
    if r.outputs:
        print(f"OUTPUTS {r.outputs}")
    if r.outcome:
        print(f"OUTCOME {r.outcome}")
    print(f"TIME    {time.time() - started:.1f}s     evidence: {r.evidence_id}")
    return r


def reset_or_exit(origin: str) -> None:
    """Restore the demo app's seed data — or say plainly that it is not running."""
    try:
        urllib.request.urlopen(f"{origin}/reset", timeout=5).read()
    except (urllib.error.URLError, OSError) as e:
        raise SystemExit(
            f"\nthe demo app is not answering at {origin} ({getattr(e, 'reason', e)}).\n"
            f"start it in another terminal, then run this again:\n"
            f"    python -m fake_bank.app                          # {origin}\n"
            f"    SKIN=bank2 PORT=5002 python -m fake_bank.app     # the second institution\n")


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
                   help=f"capability id to replay (default {DEFAULT_CAPABILITY}); see --list")
    p.add_argument("--list", action="store_true", help="show the capability catalog and exit")
    p.add_argument("--headed", action="store_true", default=os.environ.get("HEADED") == "1",
                   help="watch the browser (or HEADED=1)")
    p.add_argument("--attended", action="store_true", default=os.environ.get("ATTENDED") == "1",
                   help="an Operator is on shift: pause on escalation (or ATTENDED=1)")
    p.add_argument("--values", nargs="*", metavar="NAME=VALUE", help="other typed inputs")
    p.add_argument("--wait", type=float, default=float(os.environ.get("WAIT", "240")),
                   help="seconds to wait for an Operator when attended")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    if args.list:
        print("\nCAPABILITIES — what a caller can invoke by name\n")
        print(catalog())
        print()
        return 0
    r = run_replay(args.capability, args.member, args.tenant, headed=args.headed,
                   attended=args.attended, values=parse_values(args.values), wait_s=args.wait)
    return 0 if r.status in ("succeeded", "business_outcome") else 1


if __name__ == "__main__":
    sys.exit(main())
