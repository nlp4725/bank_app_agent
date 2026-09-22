"""The one place values are masked before they are written or sent.

Outputs are returned to the caller in full — they are the answer — but the record
of them is masked. Secrets never arrive here: they are substituted below this layer.
"""

import re

# The second net only. Patterns cannot find a name or a birthday, which is why the
# primary mechanism is origin: we mask by which field a value came from.
PATTERNS = [
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[ssn]"),
    (re.compile(r"\b(?:\d[ -]?){13,16}\b"), "[card]"),
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"), "[email]"),
    (re.compile(r"\$\d[\d,]*\.\d{2}"), "$*,***.**"),
    (re.compile(r"\b\d{4}-\d{2}-\d{2}\b"), "[date]"),
    (re.compile(r"(?<!\d)\(?\d{3}\)?[ .-]\d{3}[ .-]\d{4}(?!\d)"), "[phone]"),
]

HIDDEN = "(hidden)"
PROTECTED = "(protected)"


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


def mask_value(target_name: str | None, value: str, readable: set[str],
               is_password: bool = False) -> str:
    """Default-deny: a value is hidden unless its Target is declared readable.

    A password is never read at all, whatever the declarations say. This is what
    catches names and dates of birth — not their shape, but where they came from.
    """
    if is_password:
        return PROTECTED
    if target_name and target_name in readable:
        return redact_text(value)      # readable, but still through the net
    return HIDDEN
