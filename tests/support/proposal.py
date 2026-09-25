"""A proposal as the model returns it: the read-balance capability, well formed."""

VENDOR = "demo-core-servicing"

PROPOSAL = {
    "capability_id": "member.read_savings_balance",
    "role": "balance_reader",
    "why_this_role": "The goal only reads a value.",
    "goal": "Look up member {member_number} and read their savings balance",
    "inputs": [{"name": "member_number", "type": "string", "pattern": "^[0-9]{5}$",
                "values": None, "max_length": None, "sensitive": True, "example": "54321"}],
    "outputs": [{"name": "savings_balance", "type": "money", "sensitive": False}],
    "outcomes": [{"code": "MEMBER_NOT_FOUND", "meaning": "No such member.",
                  "resolver": "member", "caller_hint": "Re-check the number."}],
}
