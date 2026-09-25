"""The pure rules: the route a Policy is asked about is computed one way for both workflows, and a URL under another origin is asked about whole so it fails the allowlist."""

from cua.domain.rules import route_of
from cua.governance.policy import Policy, load_baseline, load_tenant_policy

# ── mid-run enforcement ───────────────────────────────────────────────────────

def test_a_url_outside_the_origin_is_asked_about_whole_and_denied():
    """One rule for both workflows. Discovery used to slice the URL by the origin's
    length, so a foreign URL could yield a path that happened to match."""
    assert route_of("http://127.0.0.1:5001/members/12345", "http://127.0.0.1:5001") == "/members/12345"
    assert route_of("http://127.0.0.1:5001", "http://127.0.0.1:5001/") == "/"
    foreign = route_of("http://attacker.example/members/12345", "http://127.0.0.1:5001")
    assert foreign == "http://attacker.example/members/12345"
    policy = Policy(baseline=load_baseline(), tenant=load_tenant_policy("bank_a", "demo-core-servicing"),
                    role_name="account_opener", vendor_app="demo-core-servicing")
    assert not policy.allows_page(foreign)
