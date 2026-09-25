"""The command-line tools: entry points that wire `cua/` together and nothing more.
Nothing in `cua/` imports from here.

One package per stage of a capability's life, in the order it happens:

    tools/start.py       the front door: a goal typed in words, both reviews, one sitting
    tools/discovery/     model in the loop — the Discovery Request, the Contract review
    tools/authoring/     draft → approved: compile, walk through, ask, apply, verify
    tools/replay/        production: replay an approved capability with no model
    tools/operator/      the Operator's side of a handoff, terminal or web
    tools/demos/         the two demonstrations, B1 and B2
    tools/inspect/       read a saved run; dump what the browser can name
    tools/_cli.py        what the tools share and the package does not need
"""
