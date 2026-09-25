"""Every file in an evidence directory leaves through the writer, and the writer
through the Redactor: an intervention request included, and a writer built with no
profile still masks text and patterns."""

from cua.evidence import EvidenceWriter


def test_an_intervention_request_leaves_through_the_redactor(tmp_path):
    """The gap this closed: Intervention.write dumped its own __dict__ into the
    evidence directory, so the one file an Operator reads never met the Redactor."""
    import json

    from cua.replay.handoff import Intervention
    writer = EvidenceWriter(tmp_path / "run_x")
    request = Intervention(run_id="run_x", capability="c", state="s", watcher=None,
                           reason="contact jane@example.com about card 4111 1111 1111 1111",
                           url="http://127.0.0.1:5001/members/12345", screenshot="")
    path = writer.intervention(request)
    writer.close()
    body = json.loads(path.read_text())
    assert "[email]" in body["reason"] and "[card]" in body["reason"]
    assert body["url"] == request.url            # what the Operator needs, still there


def test_a_writer_with_no_profile_still_masks_text_and_patterns(tmp_path):
    writer = EvidenceWriter(tmp_path)
    record = writer.event("run_x", "observed", note="card 4111 1111 1111 1111")
    writer.close()
    assert "[card]" in record["note"]
