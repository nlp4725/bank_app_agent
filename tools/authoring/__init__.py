"""Draft → approved: the second review, the Artifact — the plan of steps.

    python -m tools.authoring.record  runs/disc_x    compile a Discovery Run into a draft
    python -m tools.authoring.approve runs/disc_x    apply a decisions file, verify, approve

The interactive review `tools/start.py` runs after discovery is here in three parts:
`walkthrough` shows the draft one step at a time, `interview` asks what the Recorder
could not decide and writes the answers as a decisions file, and `review` applies
them, verify-replays on a member discovery never saw, and saves the approved Artifact.
"""
