"""Permissions are Baseline ∩ Role ∩ Tenant grant ∩ Needs, decided without a browser.

The first three are files owned by different people; each may narrow and none may
widen. The route the Policy is asked about is computed one way for both workflows.
"""

from cua.governance.policy import (
    Policy,
    load_baseline,
    load_tenant_policy,
    policy_for_role,
    route_of,
)
from cua.governance.store import origin_for

VENDOR_APP = "demo-core-servicing"

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


# ── S3: Baseline ∩ Role ∩ Tenant — every layer narrows, none widens ──────────
#
# S3 of the architecture review: a tenant file naming a route the Role did not hold used
# to grant it. Every layer narrows; none widens.

def _policy(tenant_doc, role="balance_reader"):
    return Policy(baseline=load_baseline(), tenant=tenant_doc,
                  role_name=role, vendor_app=VENDOR_APP)


def test_a_tenant_cannot_grant_a_route_its_role_does_not_hold():
    """The inversion: the tenant's list used to replace the role's, not narrow it."""
    greedy = {"tenant": "greedy", "origin": "http://x",
              "roles_granted": {"balance_reader": {}},
              "pages": ["/login", "/members/*", "/vault/*"]}
    policy = _policy(greedy)
    assert policy.allows_page("/members/12345")
    assert not policy.allows_page("/vault/gold"), \
        "a tenant policy widened the role it was granted"


def test_a_tenant_may_still_narrow_its_role():
    narrow = {"tenant": "careful", "origin": "http://x",
              "roles_granted": {"balance_reader": {}},
              "pages": ["/login"]}
    policy = _policy(narrow)
    assert policy.allows_page("/login")
    assert not policy.allows_page("/members/12345")


def test_a_tenant_that_narrows_nothing_gets_exactly_its_role():
    plain = {"tenant": "plain", "origin": "http://x",
             "roles_granted": {"balance_reader": {}}}
    policy = _policy(plain)
    assert policy.allows_page("/members/12345")
    assert not policy.allows_page("/transfers/new")


def test_the_baseline_still_refuses_what_every_layer_above_allowed():
    everything = {"tenant": "loose", "origin": "http://x",
                  "roles_granted": {"funds_mover": {}},
                  "pages": ["/transfers/*"]}
    assert not _policy(everything, "funds_mover").allows_page("/transfers/new")


def test_the_origin_comes_from_the_tenant_not_from_whichever_tool_is_running():
    policy_origin = origin_for("bank_a", VENDOR_APP)
    assert policy_origin in policy_for_role(VENDOR_APP, "balance_reader", "bank_a").origins()
