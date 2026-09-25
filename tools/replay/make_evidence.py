"""Regenerate the replay runs in evidence/ from the code as it stands.

    python -m tools.replay.make_evidence          # needs the demo app on :5001

Evidence a reader is asked to trust should be reproducible, and it should show what
the system does *now* — the committed screenshots once predated the Redactor reaching
the replay path, so they showed a member's name in the clear beside a document saying
it would be painted black. Run this after anything that changes a trail or a capture.

The two discovery folders are not regenerated: those are real model runs and cost an
API call, so they stay as recorded.
"""

import contextlib
import io
import shutil
import sys
import time
import urllib.request
from pathlib import Path

from cua.governance.store import load_capability, origin_for, overlay_for
from cua.replay.engine import RunContext, replay
from cua.replay.narration import Console
from tools.replay.run import describe

CAPABILITY = "member.open_sub_account"
VENDOR_APP = "demo-core-servicing"
EVIDENCE = Path("evidence")
INPUTS = {"member_number": "12345", "account_type": "savings", "nickname": "Live demo"}


def clears_the_flag(request, surface):
    """An Operator doing by hand what no Service Account may: signing off as themselves."""
    tb = surface.page.get_by_role("textbox")
    tb.nth(0).fill("sup_ramirez")
    tb.nth(1).fill("4821")
    surface.page.get_by_role("button", name="Acknowledge").click()
    surface.page.wait_for_load_state()
    return "resume"


RUNS = [
    ("03-replay-succeeded", "12345", "bank_a", {}),
    ("04-replay-business-outcome", "99999", "bank_a", {}),
    ("05-replay-escalation-handoff", "44444", "bank_a",
     {"attended": True, "operator": clears_the_flag}),
    ("06-replay-unknown-state", "33333", "bank_a", {}),
    ("07-replay-refused-by-policy", "12345", "bank_b", {}),
]


def one(folder, member, tenant, extra):
    art = load_capability(CAPABILITY)
    origin = origin_for(tenant, VENDOR_APP)
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        describe(art)
        print(f"\nreplaying for member {member} at {tenant} ({origin}) "
              f"— no model in the loop\n")
        with contextlib.suppress(Exception):
            urllib.request.urlopen(f"{origin}/reset", timeout=5).read()
        started = time.time()
        result = replay(art, dict(INPUTS, member_number=member),
                        RunContext(origin=origin, tenant=tenant, overlay=overlay_for(tenant),
                                   narrator=Console(slow_mo_ms=0, hold_open_s=0), **extra))
        print(f"\nRESULT  {result}")
        if result.outputs:
            print(f"OUTPUTS {result.outputs}")
        if result.outcome:
            print(f"OUTCOME {result.outcome}")
        print(f"TIME    {time.time() - started:.1f}s     evidence: {result.evidence_id}")

    target = EVIDENCE / folder
    target.mkdir(parents=True, exist_ok=True)
    for stale in target.glob("*"):
        stale.unlink()
    (target / "console.txt").write_text(out.getvalue())
    for produced in Path(result.evidence_id).iterdir():
        if produced.suffix in (".jsonl", ".png", ".json"):
            shutil.copy2(produced, target / produced.name)
    print(f"  {folder:34s} {result.status:18s} "
          f"{len(list(target.iterdir()))} files")
    return result


def main():
    print("regenerating the replay evidence\n")
    for folder, member, tenant, extra in RUNS:
        one(folder, member, tenant, extra)
    print("\ndiscovery folders left as recorded: 01, 02")


if __name__ == "__main__":
    sys.exit(main())
