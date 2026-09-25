"""The Recorder must never name an asset that is not there.

A `picture` rung is the last rung of a Target's ladder; one pointing at a file that is
gone claims a fallback the ladder does not have. So a crop is looked for beside the
run it came from, and a crop that cannot be found drops the rung and tells the
Reviewer, rather than being written down anyway.
"""

import json
import shutil
from pathlib import Path

from cua.authoring.recorder import record, record_from_run
from tools.discovery.cli import CONTRACT


def test_a_run_compiled_after_it_moved_still_finds_its_crops(tmp_path):
    """`actions.json` records the crop path the run had when it was written. Copy the
    run — into evidence/, or onto another machine — and that path is gone, but the
    crops travelled with it in screens/."""


    moved = tmp_path / "somewhere_else"
    shutil.copytree("evidence/01-discovery-goal-reached", moved)
    actions = json.loads((moved / "actions.json").read_text())
    assert any(a.get("crop", "").startswith("runs/") for a in actions), \
        "this run no longer records crops by a stale path; the test has nothing to prove"

    draft, _ = record_from_run(
        str(moved), CONTRACT,
        {"member_number": "54321", "account_type": "savings", "nickname": "Holiday fund"},
        capability_id="member.test_moved", vendor_app="demo-core-servicing",
        role="account_opener", assets_dir=tmp_path / "assets")

    pictures = [r for t in draft["targets"].values() for r in t["rungs"]
                if r["kind"] == "picture"]
    assert pictures, "the crops were beside the run and should have been found"
    for rung in pictures:
        assert Path(rung["asset"]).exists(), f"named a missing asset: {rung['asset']}"


def test_a_missing_crop_drops_the_rung_rather_than_naming_a_dead_file(tmp_path):
    """A ladder that claims a fallback it does not have is worse than a short ladder."""
    actions = [{"turn": 1, "action": "click", "role": "button", "name": "Sign in",
                "anchor": None, "target": {"rungs": [{"kind": "role_name",
                                                      "role": "button", "name": "Sign in"}]},
                "crop": "nowhere/at/all.png",
                "url_before": "http://x/login", "url_after": "http://x/search"}]
    draft, suggestions = record(actions, {"inputs": {}, "outputs": {}, "outcomes": []}, {},
                                capability_id="member.test_missing",
                                vendor_app="demo-core-servicing", role="account_opener",
                                assets_dir=tmp_path / "assets")
    rungs = [r for t in draft["targets"].values() for r in t["rungs"]]
    assert not any(r["kind"] == "picture" for r in rungs)
    assert any("crop" in s and "missing" in s for s in suggestions)
