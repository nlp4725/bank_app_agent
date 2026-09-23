"""Replay an approved artifact. No model is involved.

    python -m tools.replay 12345
    HEADED=1 python -m tools.replay 12345        # watch the browser
    python -m tools.replay 99999                 # a business outcome
    HEADED=1 python -m tools.replay 12345 lakeside   # the second institution + overlay
    HEADED=1 ATTENDED=1 python -m tools.replay 88888 # pauses for a human to take over
"""

import os
import sys
import time
import urllib.request

from cua.engine import RunContext, replay
from cua.narration import from_env
from cua.store import load_capability, origin_for, overlay_for

CAPABILITY = os.environ.get("CAPABILITY", "member.open_sub_account")   # any approved capability
VENDOR_APP = "demo-core-servicing"


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


def main():
    member = sys.argv[1] if len(sys.argv) > 1 else "12345"
    tenant = sys.argv[2] if len(sys.argv) > 2 else "bank_a"

    # One question to the Capability Store: which Artifact is live, where this Tenant
    # runs it, and what it looks like there.
    art = load_capability(CAPABILITY)
    origin = origin_for(tenant, VENDOR_APP)
    overlay = overlay_for(tenant)

    describe(art)
    if os.environ.get("ATTENDED") == "1":
        print("\nATTENDED: if this run escalates, it will pause and wait for an Operator.")
        print("  1. do what is needed in the browser it leaves open")
        print("  2. python -m tools.operator            (see the request)")
        print("  3. python -m tools.operator resume     (or: abort)")
    print(f"\nreplaying for member {member} at {tenant} ({origin}) — no model in the loop\n")

    urllib.request.urlopen(f"{origin}/reset", timeout=5).read()
    started = time.time()
    r = replay(art, {"member_number": member, "account_type": "savings",
                     "nickname": "Live demo"},
               RunContext(origin=origin, tenant=tenant, overlay=overlay,
                          headless=os.environ.get("HEADED") != "1",
                          narrator=from_env(dict(os.environ, VERBOSE="1")),
                          attended=os.environ.get("ATTENDED") == "1",
                          operator_timeout_s=float(os.environ.get("WAIT", "240"))))
    print(f"\nRESULT  {r}")
    if r.outputs:
        print(f"OUTPUTS {r.outputs}")
    if r.outcome:
        print(f"OUTCOME {r.outcome}")
    print(f"TIME    {time.time() - started:.1f}s     evidence: {r.evidence_id}")


if __name__ == "__main__":
    main()
