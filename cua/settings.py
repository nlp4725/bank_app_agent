"""Where the data lives and the few switches read from the environment, named once.

    CUA_ROOT      the directory holding config/, artifacts/ and overlays/. Defaults to
                  the repository this package sits in.
    CUA_SECRETS   "env" — secrets come from SECRET_<ACCOUNT>_<NAME> variables only;
                  "demo" — the demo app's service accounts are tried after them.
                  Defaults to "demo" only when the demo app (fake_bank/) sits beside
                  the package, so an installed copy never carries demo credentials.

Loaders read `settings` at call time, so `configure()` (or a test fixture) can point
the package at another root without restarting the process.
"""

import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_ROOT = Path(__file__).resolve().parent.parent
PROVIDERS = ("env", "demo")


@dataclass
class Settings:
    root: Path = DEFAULT_ROOT
    secrets_provider: str = "env"

    @property
    def config(self) -> Path:
        return self.root / "config"

    @property
    def roles_dir(self) -> Path:
        return self.config / "roles"

    @property
    def profiles_dir(self) -> Path:
        return self.config / "profiles"

    @property
    def policies_dir(self) -> Path:
        return self.config / "policies"

    @property
    def artifacts_dir(self) -> Path:
        return self.root / "artifacts"

    @property
    def assets(self) -> Path:
        return self.artifacts_dir / "assets"

    @property
    def overlays_dir(self) -> Path:
        return self.root / "overlays"

    @classmethod
    def from_env(cls, env=None) -> "Settings":
        env = os.environ if env is None else env
        root = Path(env.get("CUA_ROOT", DEFAULT_ROOT)).resolve()
        provider = env.get("CUA_SECRETS", "demo" if (root / "fake_bank").is_dir() else "env")
        if provider not in PROVIDERS:
            raise ValueError(f"CUA_SECRETS must be one of {PROVIDERS}, not {provider!r}")
        return cls(root=root, secrets_provider=provider)


settings = Settings.from_env()


def configure(**changes) -> Settings:
    """Change a setting for this process: `configure(root=..., secrets_provider=...)`."""
    for name, value in changes.items():
        if not hasattr(settings, name):
            raise AttributeError(f"no setting {name!r}")
        setattr(settings, name, Path(value).resolve() if name == "root" else value)
    return settings
