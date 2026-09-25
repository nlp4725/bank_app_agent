"""The Operator's side of a handoff. Deliberately minimal (the brief allows mocking the
console); the seam underneath is real — same live session, one holder at a time.

    python -m tools.operator                 show the open intervention
    python -m tools.operator resume          hand control back
    python -m tools.operator abort           stop the run
    python -m tools.operator.web             the same, as a page on http://127.0.0.1:5010
"""
