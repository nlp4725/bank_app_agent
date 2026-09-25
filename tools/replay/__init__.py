"""Production: replay an approved capability with no model in the loop.

    python -m tools.replay 12345 --headed         one replay, narrated (see cli.py for the flags)
    python -m tools.replay --list                 the catalog: what can be replayed
    python -m tools.replay.make_evidence          regenerate evidence/03…07 from the current code

`run.py` is the replay itself — one call, narrated to the console — which the other
tools import; `cli.py` is the flags around it.
"""

from tools.replay.cli import catalog, choose_capability, main, parse_args, parse_values
from tools.replay.run import describe, inputs_for, run_replay

__all__ = ["catalog", "choose_capability", "describe", "inputs_for", "main", "parse_args",
           "parse_values", "run_replay"]
