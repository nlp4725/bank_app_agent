"""Start with a goal. The interactive front door to discovery.

    python -m tools.start

    What do you want to do today?: look up a member and read their savings balance

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

    Approve this contract? [Y/n/e]  y
    member_number [54321]: 12345
    Watch the browser? [Y/n]  y

Two review points, and this file is only the conversation that joins them. The
*Contract* — the interface — is reviewed before any run (tools/discovery/contract.py);
approving it saves `contracts/<name>.yaml`, `e` saves it for editing, `n` saves nothing.
The *Artifact* — the plan of steps — is reviewed once discovery has produced a draft
(tools/authoring/review.py), and `--review runs/<id>` redoes that part alone.
"""

import argparse
import sys

from cua.discovery import ProposalError, discover, propose_contract, request_from_spec
from tools._cli import load_dotenv, report
from tools.authoring.review import review_artifact
from tools.discovery.contract import ask_values, known_outcomes, save, show, spec_for_run

VENDOR_APP = "demo-core-servicing"


def run(goal: str | None = None, *, tenant: str = "bank_a", ask=input,
        propose=propose_contract, discover_fn=discover, headed: bool | None = None,
        slowmo: int = 400, replay_fn=None, watch_fn=None) -> int:
    """The conversation. Returns a shell exit code."""
    goal = goal or ask("What do you want to do today?: ").strip()
    if not goal:
        print("Nothing to do.")
        return 1

    # A model call takes a few seconds; say so on one line, then erase it.
    print("  …", end="", flush=True)
    try:
        spec = propose(goal, VENDOR_APP, known_outcomes=known_outcomes(VENDOR_APP))
    except ProposalError as e:
        print(f"\r  could not propose a capability: {e}")
        return 1
    print("\r   \r", end="")
    print()
    print(show(spec))
    print()

    answer = (ask("Approve this contract? [Y/n/e]  ").strip().lower() or "y")
    if answer.startswith("e"):
        path = save(spec)
        print(f"\n  saved to {path} — edit it, then:\n"
              f"  python -m tools.discovery --contract {path} --headed")
        return 0
    if not answer.startswith("y"):
        print("\n  not approved; nothing saved, nothing ran.")
        return 0

    values = ask_values(spec, ask)
    spec["example_values"] = values
    path = save(spec)
    if headed is None:
        headed = (ask("Watch the browser? [Y/n]  ").strip().lower() or "y").startswith("y")

    request = request_from_spec(spec, values, tenant=tenant, headed=headed,
                                slowmo=slowmo if headed else 0)
    print(f"\n  saved to {path}\n  starting discovery for {spec['capability_id']} "
          f"at {tenant} ({request.origin})\n")
    result = discover_fn(request)
    report(result, actions=not result.draft)      # the draft shows the steps in full
    if result.draft:
        return review_artifact(spec, result.trace_dir, tenant=tenant, ask=ask, replay_fn=replay_fn,
                               watch_fn=watch_fn)
    return 0 if result.ending in ("goal_reached", "report_outcome") else 2


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m tools.start", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--goal", help="skip the first question")
    p.add_argument("--tenant", default="bank_a")
    p.add_argument("--headless", action="store_true", help="never ask; no browser window")
    p.add_argument("--review", metavar="RUN_DIR",
                   help="skip discovery: review the draft of an existing run, e.g. runs/disc_12e097f2")
    args = p.parse_args(argv)
    load_dotenv()
    try:
        if args.review:
            return review_artifact(spec_for_run(args.review), args.review, tenant=args.tenant)
        return run(args.goal, tenant=args.tenant, headed=False if args.headless else None)
    except (KeyboardInterrupt, EOFError):
        print("\nstopped.")
        return 130


if __name__ == "__main__":
    sys.exit(main())
