"""Rules with no I/O: a pattern list, a route, an input against its Contract.

Each is asked by more than one package and none needs a file, a browser or a clock,
so they live here rather than in whichever caller happened to define them first.
"""

import fnmatch
import re

from .artifact import Artifact


def covers(patterns: list[str], value: str) -> bool:
    """Is `value` permitted by any of the role's patterns?"""
    return any(fnmatch.fnmatch(value, p) or value == p for p in patterns)


def route_of(url: str, origin: str) -> str:
    """The route the Policy is asked about, from where the browser is.

    A URL that is not under the run's origin cannot be made origin-relative, so it is
    asked about whole and fails the allowlist — fail closed, rather than slicing a
    string into something that happens to match. Both workflows ask this way: the
    Discovery Run used to slice blindly.
    """
    origin = origin.rstrip("/")
    return (url[len(origin):] if url.startswith(origin) else url) or "/"


def validate_inputs(artifact: Artifact, inputs: dict) -> str | None:
    for name, spec in artifact.contract.inputs.items():
        if name not in inputs:
            if spec.required:
                return f"missing required input {name!r}"
            continue
        value = str(inputs[name])
        if spec.pattern and not re.fullmatch(spec.pattern, value):
            return f"input {name!r} does not match {spec.pattern}"
        if spec.values and value not in spec.values:
            return f"input {name!r} must be one of {spec.values}"
        if spec.max_length and len(value) > spec.max_length:
            return f"input {name!r} is longer than {spec.max_length}"
    return None
