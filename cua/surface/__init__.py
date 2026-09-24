"""The only package that touches the browser.

Everything above it works in terms of Targets, Predicates and Actions; everything
below is Playwright. Two interfaces over one driver: `Surface` acts and observes (what
the Replay Engine needs), `RecordingSurface` enumerates and describes (what a
Discovery Run needs). See driver.py for why they are split.
"""

from .driver import RecordingSurface, Resolved, Surface

__all__ = ["RecordingSurface", "Resolved", "Surface"]
