"""Before discovery: a Contract and a Role proposed from the goal.

ADR 0004: the Contract is fixed before any run. A Reviewer types the goal in words;
the model proposes the signature and the narrowest Role; the Reviewer confirms or
edits; only then does discovery start. One model call, no browser.
"""

from ..domain.artifact import Contract
from ..governance.roles import list_roles
from .model import Model

class ProposalError(Exception):
    pass


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
                     known_outcomes: list[dict] | None = None, model=None) -> dict:
    """One model call, no browser: goal in words -> Discovery Request for a Reviewer.

    `known_outcomes` are the codes other capabilities on this app already use, so the
    same answer gets the same name across the catalog."""
    roles = list_roles(vendor_app)
    roles_text = "\n".join(
        f"- {name}: {r.get('intent', '')} (consequential: {r.get('consequential', 'forbidden')};"
        f" pages: {', '.join(r.get('pages', []))})" for name, r in roles.items())
    known_text = "\n".join(f"- {o['code']}: {o.get('meaning', '')}"
                           for o in (known_outcomes or [])) or "- (none yet)"
    proposal = (model or Model(client=client)).propose(
        vendor_app=vendor_app, role_names=list(roles), roles_text=roles_text,
        known_text=known_text, goal=goal)
    if proposal is None:
        raise ProposalError("the model did not propose a capability")
    return spec_from_proposal(proposal, vendor_app)
