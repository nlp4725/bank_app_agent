"""The one place values are masked before they are written or sent.

Outputs are returned to the caller in full — they are the answer — but the record
of them is masked. Secrets never arrive here: they are substituted below this layer.
"""

import re

PATTERNS = [
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[ssn]"),
    (re.compile(r"\b(?:\d[ -]?){13,16}\b"), "[card]"),
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"), "[email]"),
    (re.compile(r"\$\d[\d,]*\.\d{2}"), "$*,***.**"),
]


def redact_text(text: str) -> str:
    for pattern, replacement in PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def redact(value, keep_values: bool = False):
    if keep_values:
        return value
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, dict):
        return {k: redact(v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    return value
