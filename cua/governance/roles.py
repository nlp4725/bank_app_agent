"""Roles: named permission bundles per vendor app, written ahead of discovery."""

from ..domain.errors import CuaError
from ..domain.rules import covers  # noqa: F401  (re-exported: callers ask roles for it)
from ..settings import settings
from .files import read_yaml


class UnknownRole(CuaError):
    pass


def _load(vendor_app: str) -> dict:
    path = settings.roles_dir / f"{vendor_app}.yaml"
    if not path.exists():
        raise UnknownRole(f"no role file for vendor app {vendor_app!r}")
    return read_yaml(path)


def list_roles(vendor_app: str) -> dict[str, dict]:
    """Every Role this vendor app defines, by name — the finite list a goal may be
    bounded by. The file also carries a `vendor_app` line, which is not a Role."""
    return {name: spec for name, spec in _load(vendor_app).items() if isinstance(spec, dict)}


def get_role(vendor_app: str, role: str) -> dict:
    roles = _load(vendor_app)
    if role not in roles or not isinstance(roles[role], dict):
        raise UnknownRole(f"{vendor_app} has no role {role!r}")
    return roles[role]
