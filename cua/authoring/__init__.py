"""Draft to approved, with no browser and no model.

The Recorder compiles a Discovery Run into a draft Artifact; the lint says what a
well-formed Artifact must also satisfy; review applies a Reviewer's decisions and
approves only if the result lints clean and a verify-replay (passed in by the caller)
succeeds. Nothing here decides anything a person did not.
"""

from .lint import lint
from .recorder import record, record_from_run
from .review import apply_decisions, approve

__all__ = ["apply_decisions", "approve", "lint", "record", "record_from_run"]
