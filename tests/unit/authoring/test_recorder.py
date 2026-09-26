"""The Recorder must never name an asset that is not there.

A `picture` rung is the last rung of a Target's ladder; one pointing at a file that is
gone claims a fallback the ladder does not have. So a crop is looked for beside the
run it came from, and a crop that cannot be found drops the rung and tells the
Reviewer, rather than being written down anyway.
"""

import json
import shutil
from pathlib import Path

from cua.authoring.recorder import record, record_from_run, watcher_from_run
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


# ── a Watcher learnt from a run that reported an outcome ─────────────────────

def _trail(tmp_path, screen: str, ending: str = "report_outcome", quote: str = "",
           code: str = "NOT_AUTHORIZED") -> Path:
    run = tmp_path / "disc_probe"
    run.mkdir()
    events = [{"event": "observed", "controls": f"[1] link \"Member Search\"\n\n"
                                               f"visible text (masked):\n{screen}"},
              {"event": "ended", "ending": ending, "outcome": code, "detail": quote}]
    (run / "trail.jsonl").write_text("\n".join(json.dumps(e) for e in events) + "\n")
    return run


def test_the_shipped_not_found_run_teaches_the_not_found_watcher():
    watcher, _ = watcher_from_run("evidence/02-discovery-business-outcome",
                                  {"member_number": "99999"})
    assert watcher == {"id": "w_member_not_found",
                       "trigger": {"type": "text_present", "value": "No records found"},
                       "condition": "business_outcome", "outcome": "MEMBER_NOT_FOUND",
                       "provenance": "discovery:02-discovery-business-outcome"}


def test_the_probed_value_becomes_a_placeholder_so_the_watcher_fits_every_member(tmp_path):
    run = _trail(tmp_path, "You are not authorized to view member 22222.",
                 quote="You are not authorized to view member 22222.")
    watcher, _ = watcher_from_run(str(run), {"member_number": "22222"})
    assert watcher["trigger"]["value"] == "You are not authorized to view member {{member_number}}."


def test_a_quote_that_was_not_on_the_screen_teaches_nothing(tmp_path):
    """The model's words are checked against what the run saw, not taken on trust."""
    run = _trail(tmp_path, "Member Search\nNo records found", quote="Member does not exist")
    watcher, why = watcher_from_run(str(run), {"member_number": "99999"})
    assert watcher is None and "not on the last screen" in why


def test_a_quote_is_cut_at_what_masking_left_in_it(tmp_path):
    """The live page shows the value, never "(hidden)": a mask in a trigger never matches."""
    run = _trail(tmp_path, "Access denied for (hidden) by policy",
                 quote="Access denied for (hidden) by policy")
    watcher, _ = watcher_from_run(str(run), {"member_number": "22222"})
    assert watcher["trigger"]["value"] == "Access denied for"


def test_a_run_that_reached_its_goal_teaches_no_outcome():
    watcher, why = watcher_from_run("evidence/01-discovery-goal-reached", {})
    assert watcher is None and "goal_reached" in why
