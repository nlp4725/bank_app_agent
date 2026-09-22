"""Permissions: Baseline ∩ Role ∩ Tenant grant ∩ Needs.

Four layers, each owned by someone different, each able only to narrow. The Baseline
is ours, a Role is written per vendor app before any discovery, the Tenant grants
roles on its own systems, and Needs are what a Discovery Run actually used.
See ADR 0005.
"""

import fnmatch
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

from .roles import get_role

CONFIG = Path(__file__).resolve().parent.parent / "config"


class PolicyError(Exception):
    pass


@lru_cache(maxsize=None)
def load_baseline() -> dict:
    return yaml.safe_load((CONFIG / "baseline.yaml").read_text())


@lru_cache(maxsize=None)
def load_tenant_policy(tenant: str, vendor_app: str) -> dict:
    path = CONFIG / "policies" / f"{tenant}.{vendor_app}.yaml"
    if not path.exists():
        raise PolicyError(f"no policy for tenant {tenant!r} on {vendor_app!r}")
    return yaml.safe_load(path.read_text())


def _covers(patterns, value) -> bool:
    return any(fnmatch.fnmatch(value, p) or value == p for p in patterns)


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
        if any(word in path.lower() for word in self.baseline["route_keywords_denied"]):
            return False
        allowed = self.tenant.get("pages") or self.role.get("pages", [])
        return _covers(allowed, path)

    def consequential_allowed(self) -> bool:
        return self.role.get("consequential") != "forbidden"

    def service_account(self) -> str:
        granted = self.tenant.get("roles_granted", {}).get(self.role_name, {})
        return granted.get("service_account") or self.role.get("service_account")

    def origin(self) -> str:
        return self.tenant.get("origin", "")

    # ── the front door ───────────────────────────────────────────────────────

    def refuse_reason(self, artifact) -> str | None:
        """Why this Artifact may not run here — checked before anything is touched."""
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


def policy_for(artifact, tenant: str) -> Policy:
    return Policy(
        baseline=load_baseline(),
        tenant=load_tenant_policy(tenant, artifact.capability.vendor_app),
        role_name=artifact.capability.role,
        vendor_app=artifact.capability.vendor_app,
    )
