"""Run one Discovery Run against the demo app.

    ANTHROPIC_API_KEY=... python -m tools.discover 54321
    ANTHROPIC_API_KEY=... python -m tools.discover 99999      # expects report_outcome
"""

import json
import sys

from cua.artifact import AppProfile
from cua.discovery import DiscoveryRequest, discover
from tests.fixtures import app_profile_dict

CONTRACT = {
    "inputs": {
        "member_number": {"type": "string", "pattern": r"^[0-9]{5}$", "sensitive": True},
        "account_type": {"type": "enum", "values": ["savings", "checking", "holiday"]},
        "nickname": {"type": "string", "max_length": 20},
    },
    "outputs": {"savings_balance": {"type": "money"}, "new_account_number": {"type": "string"}},
    "outcomes": [
        {"code": "MEMBER_NOT_FOUND", "meaning": "No member exists with that number.",
         "resolver": "member", "caller_hint": "Ask the member to re-check the number."},
        {"code": "NOT_AUTHORIZED", "meaning": "This login may not view that member.",
         "resolver": "institution_staff"},
        {"code": "VALIDATION_REJECTED", "meaning": "The application rejected the values.",
         "resolver": "member"},
    ],
}

GOAL = ("Open a savings sub-account for member {member_number} and reach the "
        "confirmation screen. Read the member's savings balance on the way.")


def main():
    member = sys.argv[1] if len(sys.argv) > 1 else "54321"
    values = {"member_number": member, "account_type": "savings", "nickname": "Holiday fund"}
    result = discover(DiscoveryRequest(
        goal=GOAL.format(**values),
        vendor_app="demo-core-servicing",
        role="account_opener",
        contract=CONTRACT,
        example_values=values,
        origin="http://127.0.0.1:5001",
        app_profile=AppProfile.model_validate(app_profile_dict()),
    ))
    print("\n=== result ===")
    print(result)
    print("outputs:", json.dumps(result.outputs, indent=2))
    print("evidence:", result.trace_dir)
    print("\n=== actions recorded ===")
    for a in result.actions:
        rungs = " -> ".join(r["kind"] for r in a["target"]["rungs"]) or "(no rungs!)"
        print(f'  {a["turn"]:2d} {a["action"]:7s} {rungs:28s} '
              f'anchor={a["anchor"]!r} value={a.get("value")!r}')


if __name__ == "__main__":
    main()
