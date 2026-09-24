"""Secrets by reference, resolved at the moment of use, never stored.

Which credential is used follows from the Role's Service Account, so a read-only
capability signs in as a login that cannot commit anything. Both workflows resolve
secrets this way; neither owns the provider, which is why it is not in the engine.

    EnvSecrets    SECRET_<ACCOUNT>_<NAME> from the environment, and nothing else
    DemoSecrets   the environment first, then the demo app's service accounts

`secrets_for` picks one by `settings.secrets_provider`, which is "demo" only when the
demo app sits beside this package (see settings.py).
"""

import os

from .domain.errors import CuaError
from .settings import settings


class MissingSecret(CuaError):
    pass


class EnvSecrets:
    """The production provider: a variable per secret, per service account."""

    def __init__(self, service_account: str):
        self.service_account = service_account

    def get(self, name: str) -> str:
        value = os.environ.get(f"SECRET_{self.service_account}_{name}".upper())
        if value is None:
            raise MissingSecret(name)
        return value


# The demo app's service accounts (fake_bank/data.py is the source of truth). They are
# used only by DemoSecrets, which is chosen only beside the demo app.
DEMO_ACCOUNTS = {
    "svc_read": {"login_username": "svc_read", "login_password": "read-only-pw"},
    "svc_officer": {"login_username": "svc_officer", "login_password": "officer-pw"},
}


class DemoSecrets(EnvSecrets):
    """The environment still wins, so a shell export overrides a demo account."""

    def get(self, name: str) -> str:
        try:
            return super().get(name)
        except MissingSecret:
            value = DEMO_ACCOUNTS.get(self.service_account, {}).get(name)
            if value is None:
                raise
            return value


def secrets_for(service_account: str) -> EnvSecrets:
    """The provider this process is configured for, for one service account."""
    if settings.secrets_provider == "demo":
        return DemoSecrets(service_account)
    return EnvSecrets(service_account)
