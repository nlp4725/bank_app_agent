"""Permissions: Baseline ∩ Role ∩ Tenant grant ∩ Needs.

Four layers, each owned by someone different, each able only to narrow. The Baseline
is ours, a Role is written per vendor app before any discovery, the Tenant grants
roles on its own systems, and Needs are what a Discovery Run actually used.
See ADR 0005.
"""

from dataclasses import dataclass
from functools import lru_cache

import yaml

from ..paths import CONFIG, POLICIES_DIR
from ..domain.rules import covers, route_of  # noqa: F401  (route_of re-exported)
from .roles import get_role


class PolicyError(Exception):
    pass



@lru_cache(maxsize=None)
def load_baseline() -> dict:
    return yaml.safe_load((CONFIG / "baseline.yaml").read_text())


@lru_cache(maxsize=None)
def load_tenant_policy(tenant: str, vendor_app: str) -> dict:
    path = POLICIES_DIR / f"{tenant}.{vendor_app}.yaml"
    if not path.exists():
        raise PolicyError(f"no policy for tenant {tenant!r} on {vendor_app!r}")
    return yaml.safe_load(path.read_text())


@dataclass
class Policy:
    baseline: dict
    tenant: dict
    role_name: str
    vendor_app: str

    @property
    def role(self) -> dict:
        return get_role(self.vendor_app, self.role_name)

    # ── what this combination permits ────────────────────────────────────────

    def allows_action(self, action: str) -> bool:
        return (action in self.baseline["actions_allowed"]
                and action in self.role.get("actions", []))

    def allows_page(self, path: str) -> bool:
        """Baseline ∩ Role ∩ Tenant. Each layer may narrow, never widen.

        The Tenant's list used to *replace* the Role's when present, so a tenant file
        naming a route the Role does not hold would have granted it — the one place
        the four-layer rule could be inverted by a config file. See ADR 0005.
        """
        if any(word in path.lower() for word in self.baseline["route_keywords_denied"]):
            return False
        if not covers(self.role.get("pages", []), path):
            return False
        narrowed = self.tenant.get("pages")
        return narrowed is None or covers(narrowed, path)

    def consequential_allowed(self) -> bool:
        return self.role.get("consequential") != "forbidden"

    def service_account(self) -> str:
        granted = self.tenant.get("roles_granted", {}).get(self.role_name, {})
        return granted.get("service_account") or self.role.get("service_account")

    def origin(self) -> str:
        """Where this Tenant's instance lives — the one automation runs against."""
        return (self.tenant.get("origin") or "").rstrip("/")

    def origins(self) -> list[str]:
        """Every instance of this Tenant's app automation may act on.

        A Tenant usually has more than one — the production instance and the
        non-production copy a Discovery Run is allowed to touch — so the Allowlist
        covers origins as well as routes. Undeclared means unreachable.
        """
        extra = self.tenant.get("origins") or []
        return [o.rstrip("/") for o in ([self.origin()] if self.origin() else []) + list(extra)]

    def allows_origin(self, origin: str) -> bool:
        return (origin or "").rstrip("/") in self.origins()

    # ── the front door ───────────────────────────────────────────────────────

    def refuse_reason(self, artifact, origin: str | None = None) -> str | None:
        """Why this Artifact may not run here — checked before anything is touched."""
        if origin is not None and not self.allows_origin(origin):
            return (f"origin {origin!r} is not an instance tenant "
                    f"{self.tenant['tenant']!r} declares")
        if self.role_name not in self.tenant.get("roles_granted", {}):
            return (f"tenant {self.tenant['tenant']!r} does not grant role "
                    f"{self.role_name!r}")
        for page in artifact.needs.pages:
            if not self.allows_page(page):
                return f"needs page {page!r}, which this tenant's policy does not grant"
        for action in artifact.needs.actions:
            if not self.allows_action(action):
                return f"needs action {action!r}, which the baseline or role does not allow"
        for secret in artifact.needs.secrets:
            if secret not in self.role.get("secrets", []):
                return f"needs secret {secret!r}, which role {self.role_name!r} does not hold"
        consequential = any(t.risk == "consequential" for t in artifact.transitions)
        if consequential and not self.consequential_allowed():
            return f"role {self.role_name!r} may not perform consequential actions"
        return None


def policy_for_role(vendor_app: str, role: str, tenant: str) -> Policy:
    """The Policy for one Role on one vendor app, as one Tenant grants it. A Discovery
    Run has no Artifact yet, so this is the form it asks in."""
    return Policy(
        baseline=load_baseline(),
        tenant=load_tenant_policy(tenant, vendor_app),
        role_name=role,
        vendor_app=vendor_app,
    )


def policy_for(artifact, tenant: str) -> Policy:
    return policy_for_role(artifact.capability.vendor_app, artifact.capability.role, tenant)
