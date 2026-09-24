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


class Redactor:
    """The Redaction Chokepoint: one module every channel passes through.

    The four layers of CONTEXT.md, "Redaction", in one place — structural (a password
    is never read), origin (a value is hidden unless its Target is a Readable Region),
    pattern (the net under what does come through), and pixels (declared Sensitive
    Regions painted black at capture). Built from the App Profile, because what is
    sensitive is a property of the app, not of one capability.

    Pixels follow the same default-deny as text: every value cell whose caption is not
    a Readable Anchor is painted, plus declared Sensitive Regions and text patterns.
    Controls are never painted — blacking out a button the model must act on would
    blind it — which is the residual risk recorded in docs/security-model.md.
    """

    def __init__(self, profile=None, *, mask_values: bool = True, mask_pixels: bool = True):
        self.profile = profile
        self.mask_values = mask_values
        self.mask_pixels = mask_pixels

    # ── what a value is allowed to be ────────────────────────────────────────

    @property
    def readable(self) -> set[str]:
        if self.profile is None:
            return set()
        return set(self.profile.readable_regions) | set(self.profile.readable_anchors)

    def text(self, value: str) -> str:
        return redact_text(value)

    def page_text(self, surface) -> str:
        """Everything visible on the page, on its way to a model: origin first, then
        patterns. Every value cell whose caption is not a Readable Anchor is replaced by
        (hidden) — a name has no shape a pattern could find, so this is the layer that
        hides it — then declared text patterns, then the pattern net over what is left.
        The same declarations paint the screenshot, so the two channels agree."""
        text = surface.text()
        if self.profile is not None and self.mask_values:
            readable = set(self.profile.readable_anchors)
            for cell in surface.values(0):
                if cell["anchor"] not in readable and cell["text"]:
                    text = text.replace(cell["text"], HIDDEN)
            for pattern in self.profile.sensitive_text:
                text = re.sub(pattern, HIDDEN, text)
        return redact_text(text)

    def fields(self, value, keep_values: bool = False):
        """Log fields and returned outputs. Outputs are the answer, so they pass
        through in full; the record of them is masked."""
        return redact(value, keep_values=keep_values)

    def value(self, anchor: str | None, raw: str, is_password: bool = False) -> str:
        """One value on screen, on its way to a model or to evidence."""
        if not self.mask_values:
            return PROTECTED if is_password else raw
        return mask_value(anchor, raw, self.readable, is_password=is_password)

    # ── pixels ───────────────────────────────────────────────────────────────

    def masked_targets(self) -> list:
        if self.profile is None or not self.mask_pixels:
            return []
        return [self.profile.targets[name] for name in self.profile.sensitive_regions
                if name in self.profile.targets]

    def screenshot(self, surface, path: str, scale: str = "css") -> str:
        """Capture with the declared Sensitive Regions already black.

        Text redaction cannot clean pixels, so this happens at capture rather than
        afterwards — and it happens here, so no caller can capture around it.
        """
        readable = (set(self.profile.readable_anchors) if self.profile is not None
                    and self.mask_pixels else None)
        patterns = tuple(self.profile.sensitive_text) if self.profile is not None \
            and self.mask_pixels else ()
        try:
            surface.screenshot(path, mask_targets=self.masked_targets(), scale=scale,
                               readable_anchors=readable, sensitive_text=patterns)
        except Exception:
            return ""
        return path


def for_app(vendor_app: str, **flags) -> Redactor:
    """The Redactor for one vendor app. An app with no Profile still gets the text
    and pattern layers, never nothing."""
    from .profile import UnknownProfile, load_profile
    try:
        return Redactor(load_profile(vendor_app), **flags)
    except UnknownProfile:
        return Redactor(None, **flags)
