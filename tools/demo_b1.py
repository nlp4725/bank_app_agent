"""B1: a control with no name, found anyway — and the log line that says how.

    python -m tools.demo_b1
"""

import urllib.request

from cua.engine import RunContext, replay
from cua.governance.store import load_capability, origin_for
from cua.surface import Surface

CAPABILITY = "member.open_sub_account"
ORIGIN = origin_for("bank_a", "demo-core-servicing")


def main():
    art = load_capability(CAPABILITY)

    print("The search control, as the browser describes it")
    print("-" * 64)
    surface = Surface(ORIGIN)
    try:
        surface.goto("/login")
        tb = surface.page.get_by_role("textbox")
        tb.nth(0).fill("svc_officer"); tb.nth(1).fill("officer-pw")
        surface.page.get_by_role("button", name="Sign in").click()
        surface.page.wait_for_load_state()
        print(surface.page.locator("body").aria_snapshot())
        print(f'  get_by_role("button", name="Search") -> '
              f'{surface.page.get_by_role("button", name="Search").count()} matches')
    finally:
        surface.close()

    print("\nIts recorded ladder")
    print("-" * 64)
    for rung in art.targets["t_member_number_button"].rungs:
        print("  ", rung.model_dump(exclude_none=True))

    print("\nReplay, and which rung actually resolved each target")
    print("-" * 64)
    urllib.request.urlopen(f"{ORIGIN}/reset").read()
    r = replay(art, {"member_number": "12345", "account_type": "savings",
                     "nickname": "B1 demo"}, RunContext(origin=ORIGIN))
    for e in r.trail:
        if e["event"] == "done" and e.get("matched_by"):
            flag = "   <-- no accessible name" if e["target"].endswith("_button") else ""
            print(f'  {e["target"]:24s} matched_by={e["matched_by"]}{flag}')
    print(f"\n  result: {r}   savings_balance={r.outputs.get('savings_balance')}")


if __name__ == "__main__":
    main()
