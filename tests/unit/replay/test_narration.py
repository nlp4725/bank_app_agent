"""How a run looks to a person watching it, behind its own seam: Silent by default."""

# ── narration is behind its own seam ─────────────────────────────────────────

def test_a_run_says_nothing_unless_somebody_is_watching():
    """Presentation used to be three knobs on RunContext and a print() in the loop."""
    from cua.replay.engine import RunContext
    from cua.replay.narration import Console, Silent, from_env

    assert RunContext(origin="http://app").narrator is None      # Silent by default
    assert Silent().slow_mo_ms == 0
    for field in ("verbose", "slow_mo_ms", "hold_open_s"):
        assert not hasattr(RunContext(origin="http://app"), field), \
            f"{field} is presentation, not run configuration"

    assert isinstance(from_env({}), Silent)
    watched = from_env({"HEADED": "1"})
    assert isinstance(watched, Console) and watched.slow_mo_ms == 900
