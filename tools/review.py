"""Apply the Reviewer's decisions to a draft, then approve only if it verifies.

    python -m tools.review runs/disc_7ec36ab5
"""

import sys
from pathlib import Path

import yaml

from cua.domain.artifact import Artifact, merged
from cua.engine import RunContext, replay
from cua.governance.profile import load_profile
from cua.authoring.recorder import record_from_run
from cua.authoring.review import apply_decisions, approve
from cua.governance.store import origin_for
from tools.discover import CONTRACT

ORIGIN = origin_for("bank_a", "demo-core-servicing")
VERIFY_INPUTS = {"member_number": "12345",      # NOT the member discovery used
                 "account_type": "savings", "nickname": "Verify run"}


def main():
    run_dir = sys.argv[1]
    draft, suggestions = record_from_run(
        run_dir, CONTRACT,
        {"member_number": "54321", "account_type": "savings", "nickname": "Holiday fund"},
        capability_id="member.open_sub_account", vendor_app="demo-core-servicing",
        role="account_opener")
    print(f"draft from {run_dir}: {len(draft['transitions'])} transitions, "
          f"{len(draft['watchers'])} watchers, status {draft['capability']['status']}")
    print("suggestions the Reviewer answered:")
    for s in suggestions:
        print("  -", s[:110])

    decisions = yaml.safe_load(Path("artifacts/open_sub_account.decisions.yaml").read_text())
    candidate = apply_decisions(draft, decisions)
    print(f"\nafter review: {len(candidate['transitions'])} transitions, "
          f"{len(candidate['watchers'])} watchers, "
          f"{sum(1 for t in candidate['transitions'] if t['risk'] == 'consequential')} consequential")

    profile = load_profile("demo-core-servicing")

    def verify(art: Artifact):
        import urllib.request
        urllib.request.urlopen(f"{ORIGIN}/reset", timeout=5).read()
        ready = Artifact.model_validate({**art.model_dump(), "capability":
                                         {**art.model_dump()["capability"], "status": "approved"}})
        return replay(merged(ready, profile), VERIFY_INPUTS, RunContext(origin=ORIGIN))

    print("\nverify-replay on member 12345 (discovery never saw it)...")
    approved, problems = approve(candidate, verify=verify)
    if approved is None:
        print("REFUSED:")
        for p in problems:
            print("  ", p)
        return
    out = Path("artifacts/open_sub_account.1.0.0.yaml")
    out.write_text(yaml.safe_dump(approved.model_dump(exclude_none=True), sort_keys=False, width=100))
    print(f"APPROVED -> {out}")


if __name__ == "__main__":
    main()
