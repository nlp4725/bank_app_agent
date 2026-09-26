"""Run one Discovery Run: a goal in words, bounded by a Role, against a Tenant's app.

    ANTHROPIC_API_KEY=... python -m tools.discovery                       # the default request
    (or put ANTHROPIC_API_KEY=... in a gitignored .env and omit it)
    ANTHROPIC_API_KEY=... python -m tools.discovery 99999                 # expects report_outcome
    ANTHROPIC_API_KEY=... python -m tools.discovery --contract contracts/read_balance.yaml
    ANTHROPIC_API_KEY=... python -m tools.discovery \\
        --goal "Look up member {member_number} and read their savings balance" \\
        --contract contracts/read_balance.yaml --role balance_reader --tenant bank_a
    python -m tools.discovery --dry-run ...                               # show the request, touch nothing

A Discovery Request is three things, and only the first is free text: the goal (the
model reads it every turn), the Role (what the goal may touch — pages, actions, whether
it may commit), and the Contract (the capability's signature, fixed before any run).
`contracts/*.yaml` holds one request per capability; every flag overrides one field.
The origin is never a flag: it comes from the Tenant's own Policy file.
"""

import argparse
import json
import os
from pathlib import Path

import yaml

from cua.discovery import DiscoveryRequest, discover, request_from_spec
from tools._cli import load_dotenv, report, require_api_key

DEFAULT_CONTRACT = Path("contracts/open_sub_account.yaml")


def load_request(path: Path = DEFAULT_CONTRACT) -> dict:
    """One Discovery Request file: capability_id, vendor_app, role, goal, contract,
    example_values."""
    return yaml.safe_load(Path(path).read_text())


# Kept by name: tools/authoring/record.py, tools/authoring/approve.py and the tests
# compile the shipped discovery run against this same Contract, so it lives in one
# file, not two.
_DEFAULT = load_request()
CONTRACT = _DEFAULT["contract"]
GOAL = _DEFAULT["goal"]
EXAMPLE_VALUES = _DEFAULT["example_values"]


def parse_values(pairs: list[str]) -> dict:
    values = {}
    for pair in pairs:
        if "=" not in pair:
            raise SystemExit(f"--values takes name=value pairs, not {pair!r}")
        name, value = pair.split("=", 1)
        values[name.strip()] = value
    return values


def build(args) -> DiscoveryRequest:
    spec = load_request(args.contract)
    values = dict(spec.get("example_values", {}))
    if args.member:
        values["member_number"] = args.member
    values.update(parse_values(args.values))
    return request_from_spec(spec, values, tenant=args.tenant, headed=args.headed,
                             slowmo=args.slowmo, goal=args.goal, role=args.role,
                             capability=args.capability)


def describe(request: DiscoveryRequest) -> str:
    contract = request.contract
    return "\n".join([
        f"  goal        {request.goal}",
        f"  capability  {request.capability_id}",
        f"  vendor app  {request.vendor_app}",
        f"  role        {request.role}",
        f"  tenant      {request.tenant}  ->  {request.origin}",
        f"  inputs      {', '.join(contract.get('inputs', {}))}",
        f"  outputs     {', '.join(contract.get('outputs', {}))}",
        f"  outcomes    {', '.join(o['code'] for o in contract.get('outcomes', []))}",
        f"  values      {json.dumps(request.example_values)}",
    ])


def parse_args(argv=None):
    p = argparse.ArgumentParser(prog="python -m tools.discovery", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("member", nargs="?", help="member number (shorthand for --values member_number=…)")
    p.add_argument("--goal", help="the goal, in words; {name} is filled from --values")
    p.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT,
                   help=f"Discovery Request file (default: {DEFAULT_CONTRACT})")
    p.add_argument("--role", help="Role that bounds the goal (default: the file's)")
    p.add_argument("--tenant", default="bank_a",
                   help="whose instance to discover against; the origin comes from its Policy")
    p.add_argument("--capability", help="capability id for the draft (default: the file's)")
    p.add_argument("--values", nargs="*", default=[], metavar="NAME=VALUE",
                   help="example input values, overriding the file's")
    p.add_argument("--headed", action="store_true", default=os.environ.get("HEADED") == "1",
                   help="show the browser (or HEADED=1)")
    p.add_argument("--slowmo", type=int, default=int(os.environ.get("SLOWMO", "0")),
                   help="ms between actions, so a person can follow (or SLOWMO=…)")
    p.add_argument("--dry-run", action="store_true",
                   help="print the resolved request and exit; no browser, no model")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    load_dotenv()
    request = build(args)
    print("\n=== discovery request ===")
    print(describe(request))
    if args.dry_run:
        return

    require_api_key()
    report(discover(request))


if __name__ == "__main__":
    main()
