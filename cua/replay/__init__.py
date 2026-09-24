"""The production path: execute an approved Artifact with no model in the loop.

`replay()` is the front door. It reaches governance, evidence, the surface and the
secrets provider, and nothing that imports a model SDK — a boundary test walks the
import graph from engine.py to say so.
"""

from ..domain.result import RunResult
from .engine import RunContext, replay, validate_inputs
from .narration import Console, Silent, from_env

__all__ = ["Console", "RunContext", "RunResult", "Silent", "from_env", "replay",
           "validate_inputs"]
