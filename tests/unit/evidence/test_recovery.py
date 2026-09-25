"""The write-ahead log detects a death mid-commit.

S1 of the architecture review: each Consequential Action is written down before it is
performed and again after, so a run that stopped between the two is found on restart
and answered as Outcome Unknown, not silence. The live half — a real run leaves a trail
the detector reads — is in tests/app/test_outcome_unknown.py.
"""

import json

from cua.evidence import unfinished


def write_trail(directory, lines):
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "trail.jsonl").write_text("\n".join(json.dumps(l) for l in lines))


def test_a_run_that_died_mid_commit_is_found_on_restart(tmp_path):
    write_trail(tmp_path / "run_dead", [
        {"run_id": "run_dead", "event": "about_to", "step": "review_shown",
         "action": "click", "target": "t_commit", "risk": "consequential"},
    ])
    found = unfinished(tmp_path)
    assert len(found) == 1
    assert found[0]["status"] == "outcome_unknown"
    assert found[0]["step"] == "review_shown"


def test_a_run_that_finished_its_commit_is_not_reported(tmp_path):
    write_trail(tmp_path / "run_ok", [
        {"run_id": "run_ok", "event": "about_to", "step": "review_shown",
         "action": "click", "target": "t_commit", "risk": "consequential"},
        {"run_id": "run_ok", "event": "done", "step": "review_shown"},
        {"run_id": "run_ok", "event": "result", "status": "succeeded"},
    ])
    assert unfinished(tmp_path) == []


def test_a_run_that_died_before_anything_consequential_is_not_reported(tmp_path):
    write_trail(tmp_path / "run_early", [
        {"run_id": "run_early", "event": "about_to", "step": "sign_in",
         "action": "type", "target": "t_user", "risk": "safe"},
    ])
    assert unfinished(tmp_path) == []
