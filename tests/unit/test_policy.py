"""Permissions are Baseline ∩ Role ∩ Tenant grant ∩ Needs, decided without a browser.

The first three are files owned by different people; each may narrow and none may
widen. The route the Policy is asked about is computed one way for both workflows.
"""

from cua.governance.policy import Policy, load_baseline, load_tenant_policy, route_of

# ── policy layering, without a browser ───────────────────────────────────────

def test_a_tenant_may_narrow_the_baseline_never_widen_it():
    baseline = load_baseline()
    tenant = load_tenant_policy("bank_a", "demo-core-servicing")
    policy = Policy(baseline=baseline, tenant=tenant, role_name="account_opener",
                    vendor_app="demo-core-servicing")
    assert policy.allows_action("click")
    assert not policy.allows_action("download")       # the baseline forbids it
    assert policy.allows_page("/members/12345")
    assert not policy.allows_page("/admin")           # keyword deny plus route allowlist


def test_a_read_only_role_may_not_commit():
    baseline = load_baseline()
    tenant = load_tenant_policy("bank_a", "demo-core-servicing")
    policy = Policy(baseline=baseline, tenant=tenant, role_name="balance_reader",
                    vendor_app="demo-core-servicing")
    assert policy.consequential_allowed() is False
    assert policy.service_account() == "svc_read"


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
