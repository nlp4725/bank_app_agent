"""Compile a Discovery Run into a draft Artifact.

    python -m tools.authoring.record runs/disc_e9d8f68f
"""

import sys
from pathlib import Path

import yaml

from cua.authoring.lint import lint
from cua.authoring.recorder import record_from_run
from cua.domain.artifact import Artifact
from tools.discovery.cli import CONTRACT, EXAMPLE_VALUES


def main():
    run_dir = sys.argv[1]
    member = sys.argv[2] if len(sys.argv) > 2 else EXAMPLE_VALUES["member_number"]
    draft, suggestions = record_from_run(
        run_dir, CONTRACT, dict(EXAMPLE_VALUES, member_number=member),
        capability_id="member.open_sub_account", vendor_app="demo-core-servicing",
        role="account_opener")

    out = Path("artifacts/open_sub_account.draft.yaml")
    out.parent.mkdir(exist_ok=True)
    out.write_text(yaml.safe_dump(draft, sort_keys=False, width=100))
    print(yaml.safe_dump(draft, sort_keys=False, width=100))

    print("=== schema ===")
    art = Artifact.model_validate(draft)
    print("parses OK:", art.capability.id, art.capability.status)
    print("\n=== lint ===")
    issues = lint(art)
    print("\n".join(f"  {i}" for i in issues) or "  no issues")
    print("\n=== suggestions for the Reviewer ===")
    print("\n".join(f"  - {s}" for s in suggestions))
    print(f"\nwritten to {out}")


if __name__ == "__main__":
    main()
