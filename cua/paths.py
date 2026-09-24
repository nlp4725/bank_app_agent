"""Where the repository keeps its data, named once.

Five modules used to compute the repository root from their own `__file__`, so
moving any of them one directory down changed the arithmetic. Everything that
reads config or artifacts takes its directories from here.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config"
ROLES_DIR = CONFIG / "roles"
PROFILES_DIR = CONFIG / "profiles"
POLICIES_DIR = CONFIG / "policies"
ARTIFACTS_DIR = ROOT / "artifacts"
ASSETS = ARTIFACTS_DIR / "assets"
OVERLAYS_DIR = ROOT / "overlays"
