"""Input placeholders: `{{name}}` in an Artifact, filled from the run's inputs.

One regex, used by the engine to render and by the linter to check, so the two
cannot disagree about what a placeholder looks like.
"""

import re

PLACEHOLDER = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")


def render(value: str, inputs: dict) -> str:
    """Substitute the run's inputs. An unknown placeholder is left as written, so it
    shows up in evidence as itself rather than as an empty string."""
    return PLACEHOLDER.sub(lambda m: str(inputs.get(m.group(1), m.group(0))), value)
