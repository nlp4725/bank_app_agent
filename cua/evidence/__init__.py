"""Every log line, screenshot and result leaves through here.

One writer, one Redactor in front of it, and one reader that recognises a run that
died with a Consequential Action in flight.
"""

from .recovery import unfinished
from .redact import HIDDEN, PROTECTED, Redactor, mask_value, redact_text
from .writer import EvidenceWriter

__all__ = ["EvidenceWriter", "HIDDEN", "PROTECTED", "Redactor", "mask_value",
           "redact_text", "unfinished"]
