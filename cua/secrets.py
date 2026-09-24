"""Secrets by reference, resolved at the moment of use, never stored.

Which credential is used follows from the Role's Service Account, so a read-only
capability signs in as a login that cannot commit anything. Both workflows resolve
secrets this way; neither owns the provider, which is why it is not in the engine.
"""

import os


class MissingSecret(Exception):
    pass


DEMO_ACCOUNTS = {           # the demo app only; documented in the README
    "svc_read": {"login_username": "svc_read", "login_password": "read-only-pw"},
    "svc_officer": {"login_username": "svc_officer", "login_password": "officer-pw"},
}


class EnvSecrets:
    def __init__(self, service_account: str = "svc_officer"):
        self.service_account = service_account

    def get(self, name: str) -> str:
        value = os.environ.get(f"SECRET_{self.service_account}_{name}".upper())
        if value is None:
            value = DEMO_ACCOUNTS.get(self.service_account, {}).get(name)
        if value is None:
            raise MissingSecret(name)
        return value
