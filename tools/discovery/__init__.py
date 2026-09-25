"""Model in the loop, once per capability.

    python -m tools.discovery ...            one Discovery Run from a request file and flags
    python -m tools.discovery.smoke_llm      one turn against the real model: does the plumbing work?

`contract.py` is the first review — the Contract, shown and confirmed before any run —
which `tools/start.py` asks at the prompt. `cli.py` is the same request built from flags.
"""
