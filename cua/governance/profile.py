"""The App Profile for one vendor app, loaded from config.

Session expiry, interstitials, error pages and the Readable/Sensitive Regions are
properties of the app, not of any one capability: learnt once, they reach every
Artifact. They are governance data a Reviewer owns, so they live beside the Roles in
`config/`, not inside any caller. See docs/CONTEXT.md, "App Profile".
"""

from functools import cache

from ..domain.artifact import AppProfile
from ..domain.errors import CuaError
from ..evidence.redact import Redactor
from ..settings import settings
from .files import read_yaml


class UnknownProfile(CuaError):
    pass


def load_profile(vendor_app: str) -> AppProfile:
    path = settings.profiles_dir / f"{vendor_app}.yaml"
    if not path.exists():
        raise UnknownProfile(f"no app profile for vendor app {vendor_app!r}")
    return _profile(path)


@cache
def _profile(path) -> AppProfile:
    return AppProfile.model_validate(read_yaml(path))


def redactor_for(vendor_app: str, **flags) -> Redactor:
    """The Redactor for one vendor app. An app with no Profile still gets the text
    and pattern layers, never nothing."""
    try:
        return Redactor(load_profile(vendor_app), **flags)
    except UnknownProfile:
        return Redactor(None, **flags)
