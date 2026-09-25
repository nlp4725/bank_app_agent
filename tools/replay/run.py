"""One replay, narrated to the console.

Which artifact runs is the Capability Store's answer (cua/governance/store.py): the
highest *approved* version of the capability id — a draft never replays.
"""

import os
import time

from cua.governance.store import load_capability, origin_for, overlay_for
from cua.replay.engine import RunContext, replay
from cua.replay.narration import from_env
from tools._cli import reset_or_exit

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


def inputs_for(art, member: str, given: dict | None = None) -> dict:
    """The typed inputs this contract needs: the member, what the caller gave, and demo
    values for the rest — never an input the contract does not declare."""
    values = {"member_number": member, **DEMO_VALUES, **(given or {})}
    return {name: values[name] for name in art.contract.inputs if name in values}


def run_replay(capability: str, member: str, tenant: str = "bank_a", *, headed: bool = False,
               attended: bool = False, values: dict | None = None, wait_s: float = 240.0,
               slowmo_ms: int | None = None):
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
    if slowmo_ms is not None:
        env["SLOWMO"] = str(slowmo_ms)          # ms between steps, so a person can follow
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
