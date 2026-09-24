"""Before discovery: a Contract and a Role proposed from the goal.

ADR 0004: the Contract is fixed before any run. A Reviewer types the goal in words;
the model proposes the signature and the narrowest Role; the Reviewer confirms or
edits; only then does discovery start. One model call, no browser.
"""

import anthropic

from ..domain.artifact import Contract
from ..governance.roles import list_roles
from .run import MODEL

PROPOSE_SYSTEM = """You design the interface of one automation capability for a bank
member-servicing application, from a goal a reviewer typed in plain words.

You propose four things and nothing else:

1. The narrowest Role that can do the goal. A role whose `consequential` is `forbidden`
   cannot create, change or move anything; choose it whenever the goal only looks
   something up or reads a value.

2. The typed inputs the caller must supply each time. A member number is a 5-digit
   string, pattern ^[0-9]{5}$, sensitive. Never make a credential an input.

3. The typed outputs — only what the goal asks for, nothing the goal did not mention.
   Name them by what they are on a bank screen: `savings_balance`, not `account_balance`;
   a balance is `money`. A person's name, date of birth, address, phone, email or SSN is
   always `sensitive: true`.

4. The business outcomes: every legitimate answer the application can give that makes
   the goal impossible for these inputs. These are answers the caller acts on, not
   errors. Enumerate them deliberately:
   - looking a member up: MEMBER_NOT_FOUND (resolver member) and NOT_AUTHORIZED
     (resolver institution_staff), always;
   - for every output, the case where a valid member simply has no such value —
     e.g. reading a savings balance implies NO_SAVINGS_ACCOUNT (resolver member);
   - submitting a form: VALIDATION_REJECTED (resolver member);
   - creating or changing something: whatever limit or hold the app may answer with,
     e.g. MAX_ACCOUNTS_REACHED, ACCOUNT_ON_HOLD (resolver institution_staff).
   Do not list session expiry, slowness, application errors or interstitials: those are
   runtime conditions the engine recovers from, not answers.
   When a code is already in use on this application, reuse that exact name.

Restate the goal with `{input_name}` where an input value goes. Keep names snake_case.
The capability id is `member.<verb>_<noun>`."""


class ProposalError(Exception):
    pass


def propose_tool(role_names: list[str]) -> dict:
    def obj(props, required):
        return {"type": "object", "properties": props, "required": required,
                "additionalProperties": False}
    nullable_str = {"type": ["string", "null"]}
    return {
        "name": "propose_capability",
        "description": "The proposed interface of the capability.",
        "strict": True,
        "input_schema": obj({
            "capability_id": {"type": "string"},
            "role": {"type": "string", "enum": role_names},
            "why_this_role": {"type": "string", "description": "one short sentence"},
            "goal": {"type": "string",
                     "description": "the goal restated with {input_name} placeholders"},
            "inputs": {"type": "array", "items": obj({
                "name": {"type": "string"},
                "type": {"type": "string", "enum": ["string", "enum"]},
                "pattern": nullable_str,
                "values": {"anyOf": [{"type": "array", "items": {"type": "string"}},
                                     {"type": "null"}]},
                "max_length": {"type": ["integer", "null"]},
                "sensitive": {"type": "boolean"},
                "example": {"type": "string", "description": "a plausible example value"},
            }, ["name", "type", "pattern", "values", "max_length", "sensitive", "example"])},
            "outputs": {"type": "array", "items": obj({
                "name": {"type": "string"},
                "type": {"type": "string", "enum": ["string", "money", "date", "integer"]},
                "sensitive": {"type": "boolean"},
            }, ["name", "type", "sensitive"])},
            "outcomes": {"type": "array", "items": obj({
                "code": {"type": "string"},
                "meaning": {"type": "string"},
                "resolver": {"type": "string", "enum": ["member", "institution_staff", "nobody"]},
                "caller_hint": nullable_str,
            }, ["code", "meaning", "resolver", "caller_hint"])},
        }, ["capability_id", "role", "why_this_role", "goal", "inputs", "outputs", "outcomes"]),
    }


def spec_from_proposal(proposal: dict, vendor_app: str) -> dict:
    """The model's answer as a Discovery Request, validated against the Contract
    schema the engine runs. A shape the engine does not know is refused here."""

    if proposal.get("role") not in list_roles(vendor_app):
        raise ProposalError(f"proposed role {proposal.get('role')!r} is not a Role of {vendor_app}")

    inputs, examples = {}, {}
    for i in proposal.get("inputs", []):
        spec = {"type": i["type"], "sensitive": bool(i.get("sensitive"))}
        if i.get("pattern"):
            spec["pattern"] = i["pattern"]
        if i.get("values"):
            spec["values"] = list(i["values"])
        if i.get("max_length"):
            spec["max_length"] = int(i["max_length"])
        inputs[i["name"]] = spec
        examples[i["name"]] = i.get("example", "")
    outputs = {o["name"]: {"type": o["type"], "sensitive": bool(o.get("sensitive"))}
               for o in proposal.get("outputs", [])}
    outcomes = []
    for o in proposal.get("outcomes", []):
        entry = {"code": o["code"], "meaning": o["meaning"], "resolver": o["resolver"]}
        if o.get("caller_hint"):
            entry["caller_hint"] = o["caller_hint"]
        outcomes.append(entry)

    contract = {"inputs": inputs, "outputs": outputs, "outcomes": outcomes}
    try:
        Contract.model_validate(contract)
    except Exception as e:                       # pydantic's message names the field
        raise ProposalError(f"the proposal is not a valid Contract: {e}") from e
    if not outputs and not outcomes:
        raise ProposalError("a capability returns something: no outputs and no outcomes")

    return {
        "capability_id": proposal["capability_id"],
        "vendor_app": vendor_app,
        "role": proposal["role"],
        "why_this_role": proposal.get("why_this_role", ""),
        "goal": proposal["goal"],
        "example_values": examples,
        "contract": contract,
    }


def propose_contract(goal: str, vendor_app: str, client=None,
                     known_outcomes: list[dict] | None = None) -> dict:
    """One model call, no browser: goal in words -> Discovery Request for a Reviewer.

    `known_outcomes` are the codes other capabilities on this app already use, so the
    same answer gets the same name across the catalog."""
    roles = list_roles(vendor_app)
    roles_text = "\n".join(
        f"- {name}: {r.get('intent', '')} (consequential: {r.get('consequential', 'forbidden')};"
        f" pages: {', '.join(r.get('pages', []))})" for name, r in roles.items())
    known_text = "\n".join(f"- {o['code']}: {o.get('meaning', '')}"
                           for o in (known_outcomes or [])) or "- (none yet)"
    client = client or anthropic.Anthropic()
    response = client.messages.create(
        model=MODEL, max_tokens=1024, system=PROPOSE_SYSTEM,
        tools=[propose_tool(list(roles))],
        tool_choice={"type": "tool", "name": "propose_capability"},
        messages=[{"role": "user", "content":
                   f"application: {vendor_app}\nroles available:\n{roles_text}\n\n"
                   f"outcome codes already in use on this application:\n{known_text}\n\n"
                   f"goal, as the reviewer typed it: {goal}"}],
    )
    call = next((b for b in response.content if b.type == "tool_use"), None)
    if call is None:
        raise ProposalError("the model did not propose a capability")
    return spec_from_proposal(call.input, vendor_app)
