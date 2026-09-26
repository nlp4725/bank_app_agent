"""The first review: the Contract — the interface — before any run.

A goal typed in words becomes a proposed Contract and Role; the Reviewer sees it as
below, confirms the example values against the Contract's own rules, and approving it
saves `contracts/<name>.yaml`. `tools/start.py` asks these questions at the prompt.

      capability  member.read_savings_balance
      role        balance_reader — View member information and balances.
      inputs      member_number   string  ^[0-9]{5}$  (sensitive)

      returns     succeeded         -> outputs:
                                       savings_balance    money
                  business_outcome  -> one of:
                                       MEMBER_NOT_FOUND   resolver: member
                                       NOT_AUTHORIZED     resolver: institution_staff
                                       NO_SAVINGS_ACCOUNT resolver: member
                  failed | refused | aborted | outcome_unknown  (engine; not reviewed here)
"""

import re
from pathlib import Path

import yaml

from cua.governance.roles import get_role

CONTRACTS = Path("contracts")


def known_outcomes(vendor_app: str) -> list[dict]:
    """Outcome codes the other Discovery Requests on this app already use, by code."""
    seen = {}
    for path in sorted(CONTRACTS.glob("*.yaml")):
        spec = yaml.safe_load(path.read_text()) or {}
        if spec.get("vendor_app") != vendor_app:
            continue
        for o in spec.get("contract", {}).get("outcomes", []):
            seen.setdefault(o["code"], o)
    return list(seen.values())


def show(spec: dict) -> str:
    role = get_role(spec["vendor_app"], spec["role"])
    c = spec["contract"]
    lines = [f"  capability  {spec['capability_id']}",
             f"  role        {spec['role']} — {role.get('intent', '')}"
             + (f"\n              ({spec['why_this_role']})" if spec.get("why_this_role") else ""),
             f"  goal        {spec['goal']}"]
    for name, i in c["inputs"].items():
        rule = i.get("pattern") or (f"one of {', '.join(i['values'])}" if i.get("values") else "")
        rule = rule or (f"≤ {i['max_length']} chars" if i.get("max_length") else "")
        lines.append(f"  input       {name:18s} {i['type']:7s} {rule}"
                     + ("  (sensitive)" if i.get("sensitive") else ""))
    lines.append("")
    lines.append("  returns     succeeded         -> outputs:")
    for name, o in c["outputs"].items():
        lines.append(f"                                   {name:18s} {o['type']}"
                     + ("  (sensitive)" if o.get("sensitive") else ""))
    lines.append("              business_outcome  -> one of:")
    for o in c["outcomes"]:
        lines.append(f"                                   {o['code']:18s} resolver: {o['resolver']}")
    if not c["outcomes"]:
        lines.append("                                   (none proposed)")
    lines.append("              failed | refused | aborted | outcome_unknown  (engine; not reviewed here)")
    return "\n".join(lines)


def check(spec_in: dict, value: str) -> str | None:
    """Why this value is not acceptable for this input, or None."""
    if spec_in.get("pattern") and not re.fullmatch(spec_in["pattern"], value):
        return f"must match {spec_in['pattern']}"
    if spec_in.get("values") and value not in spec_in["values"]:
        return f"must be one of {', '.join(spec_in['values'])}"
    if spec_in.get("max_length") and len(value) > spec_in["max_length"]:
        return f"at most {spec_in['max_length']} characters"
    return None


def ask_values(spec: dict, ask=input) -> dict:
    values = {}
    for name, i in spec["contract"]["inputs"].items():
        default = spec.get("example_values", {}).get(name, "")
        while True:
            raw = ask(f"{name} [{default}]: " if default else f"{name}: ").strip() or default
            problem = check(i, raw)
            if problem is None and raw:
                values[name] = raw
                break
            print(f"  {name}: {problem or 'a value is needed'}")
    return values


def ask_outcome_examples(spec: dict, ask=input) -> dict:
    """Per Outcome Code, the inputs that should produce it: discovery probes each one
    so the screen that means it is learnt rather than typed. Test data a tester knows —
    "99999 does not exist" — kept in the Discovery Request file once given.

    Values already in the file for this capability are kept without asking. Otherwise
    the first input is asked for (the others stay as the happy path's); Enter skips
    the outcome, which the review then drops unless a Watcher can be borrowed."""
    first = next(iter(spec["contract"]["inputs"]), None)
    codes = [o["code"] for o in spec["contract"]["outcomes"]]
    kept = {c: v for c, v in (spec.get("outcome_examples") or previous(spec).get(
        "outcome_examples") or {}).items() if c in codes}
    for code in codes:
        if code in kept or first is None:
            continue
        rule = spec["contract"]["inputs"][first]
        while True:
            raw = ask(f"  {first} that gives {code} (Enter to skip): ").strip()
            raw = "" if raw.lower() in ("n", "no") else raw
            problem = check(rule, raw) if raw else None
            if problem is None:
                break
            print(f"    {first}: {problem}")
        if raw:
            kept[code] = {first: raw}
    return kept


def previous(spec: dict) -> dict:
    """The saved Discovery Request for this capability, if there is one."""
    path = CONTRACTS / f"{spec['capability_id'].split('.')[-1]}.yaml"
    return (yaml.safe_load(path.read_text()) or {}) if path.exists() else {}


def save(spec: dict) -> Path:
    CONTRACTS.mkdir(exist_ok=True)
    stem = spec["capability_id"].split(".")[-1]
    path = CONTRACTS / f"{stem}.yaml"
    out = {k: spec[k] for k in ("capability_id", "vendor_app", "role", "goal",
                                "example_values", "outcome_examples", "contract") if k in spec}
    path.write_text("# Proposed by the model from a goal typed in words; confirmed by a "
                    "Reviewer in tools.start.\n" + yaml.safe_dump(out, sort_keys=False, width=100))
    return path


def spec_for_run(run_dir: str) -> dict:
    """The Discovery Request a run was made from, by its draft's capability id."""
    draft = yaml.safe_load((Path(run_dir) / "draft.yaml").read_text())
    stem = draft["capability"]["id"].split(".")[-1]
    path = CONTRACTS / f"{stem}.yaml"
    if not path.exists():
        raise SystemExit(f"no {path} for {draft['capability']['id']}")
    return yaml.safe_load(path.read_text())
