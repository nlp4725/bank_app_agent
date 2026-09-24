"""The App Profile for one vendor app, loaded from config.

Session expiry, interstitials, error pages and the Readable/Sensitive Regions are
properties of the app, not of any one capability: learnt once, they reach every
Artifact. They are governance data a Reviewer owns, so they live beside the Roles in
`config/`, not inside any caller. See CONTEXT.md, "App Profile".
"""

from functools import lru_cache

import yaml

from .domain.artifact import AppProfile
from .paths import PROFILES_DIR


class UnknownProfile(Exception):
    pass


@lru_cache(maxsize=None)
def load_profile(vendor_app: str) -> AppProfile:
    path = PROFILES_DIR / f"{vendor_app}.yaml"
    if not path.exists():
        raise UnknownProfile(f"no app profile for vendor app {vendor_app!r}")
    return AppProfile.model_validate(yaml.safe_load(path.read_text()))
