"""The driver's request gate, against the running app: a request the page starts by itself to another origin is aborted in the browser, not merely logged."""

from cua.surface import Surface

# ── mid-run enforcement ───────────────────────────────────────────────────────

def test_a_request_to_another_origin_is_aborted_in_the_browser(bank_app):
    """The page, not us, starts this one: an <img> pointing off-site.

    A check before we act cannot see it, so the allowlist is enforced on every
    request the browser makes.
    """
    surface = Surface(bank_app)
    try:
        surface.goto("/leaky")
        surface.page.wait_for_timeout(800)
        blocked = surface.blocked_requests
        assert any("attacker.example" in url for url in blocked), blocked
    finally:
        surface.close()
