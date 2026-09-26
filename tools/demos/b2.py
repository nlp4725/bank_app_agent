"""B2: one artifact, two institutions on the same vendor product.

    python -m tools.demos.b2

Recorded against First Credit Union. Run unchanged against Lakeside Savings, which
renamed the controls and moved the search icon — first without an Overlay, then with.
The capability commits, so it only runs attended: a scripted Operator approves the
commit and declines to take over a screen the Artifact does not recognise.
"""

import urllib.request

from cua.governance.store import load_capability, origin_for, overlay_for
from cua.replay.engine import RunContext, replay
from tools._cli import scripted_operator

CAPABILITY = "member.open_sub_account"
BANK1 = origin_for("bank_a", "demo-core-servicing")
BANK2 = origin_for("lakeside", "demo-core-servicing")
INPUTS = {"member_number": "12345", "account_type": "savings", "nickname": "B2 demo"}


def run(art, origin, tenant, overlay=None):
    urllib.request.urlopen(f"{origin}/reset").read()
    return replay(art, INPUTS, RunContext(origin=origin, tenant=tenant, overlay=overlay,
                                          attended=True, operator=scripted_operator))


def handed_over_because(result) -> str:
    """Why the run stopped and asked its Operator, from its trail."""
    return next((e.get("reason") for e in result.trail
                 if e["event"] == "intervention_raised"), "") or "no handover"


def main():
    art = load_capability(CAPABILITY)
    overlay = overlay_for("lakeside")

    print("1. First Credit Union — the institution it was recorded on")
    print(f"   {run(art, BANK1, 'bank_a')}\n")

    print("2. Lakeside Savings — same product, renamed controls, no Overlay")
    r = run(art, BANK2, "lakeside")
    print(f"   {r}")
    print(f"   handed to the Operator because: {handed_over_because(r)}\n")

    print("3. Lakeside Savings — the same artifact, with a 20-line Overlay")
    r = run(art, BANK2, "lakeside", overlay)
    print(f"   {r}   savings_balance={r.outputs.get('savings_balance')} "
          f"account={r.outputs.get('new_account_number')}")
    print("   patched:", ", ".join(sorted(overlay["targets"])))

    print("\n4. An Overlay that tries to change behaviour")
    bad = dict(overlay, transitions=[{"from_state": "s1_login", "to_state": "s2_search",
                                      "action": {"type": "click", "target": "t_open"}}])
    print(f"   {run(art, BANK2, 'lakeside', bad)}")


if __name__ == "__main__":
    main()
