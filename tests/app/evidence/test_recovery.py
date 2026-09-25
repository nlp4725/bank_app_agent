"""The trail reader against a real run: a completed run must not look unfinished. The reader's own rules are tests/unit/evidence/test_recovery.py."""

from cua.evidence import unfinished
from cua.replay.engine import RunContext, replay
from tests.support.doubles import attended


def test_a_real_run_leaves_a_trail_the_detector_reads(artifact, bank_app, tmp_path):
    replay(artifact, {"member_number": "12345", "account_type": "savings",
                      "nickname": "Holiday fund"},
           RunContext(origin=bank_app, evidence_root=str(tmp_path), **attended()))
    assert unfinished(tmp_path) == [], "a completed run must not look unfinished"
