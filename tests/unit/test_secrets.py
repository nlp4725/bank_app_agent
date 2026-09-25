"""Secrets by reference: the environment provider knows nothing of demo accounts, the demo provider lets the environment win, and the setting chooses between them."""

import pytest

from cua.secrets import DemoSecrets, EnvSecrets, MissingSecret, secrets_for
from cua.settings import configure, settings


@pytest.fixture
def restore_settings():
    before = (settings.root, settings.secrets_provider)
    yield
    configure(root=before[0], secrets_provider=before[1])


def test_the_env_provider_knows_nothing_of_demo_accounts(monkeypatch):
    monkeypatch.delenv("SECRET_SVC_READ_LOGIN_PASSWORD", raising=False)
    with pytest.raises(MissingSecret):
        EnvSecrets("svc_read").get("login_password")
    monkeypatch.setenv("SECRET_SVC_READ_LOGIN_PASSWORD", "from-the-shell")
    assert EnvSecrets("svc_read").get("login_password") == "from-the-shell"


def test_the_demo_provider_lets_the_environment_win(monkeypatch):
    monkeypatch.delenv("SECRET_SVC_READ_LOGIN_PASSWORD", raising=False)
    assert DemoSecrets("svc_read").get("login_password") == "read-only-pw"
    monkeypatch.setenv("SECRET_SVC_READ_LOGIN_PASSWORD", "from-the-shell")
    assert DemoSecrets("svc_read").get("login_password") == "from-the-shell"
    with pytest.raises(MissingSecret):
        DemoSecrets("svc_read").get("api_token")


def test_the_provider_is_chosen_by_the_setting(restore_settings):
    configure(secrets_provider="env")
    assert type(secrets_for("svc_read")) is EnvSecrets
    configure(secrets_provider="demo")
    assert type(secrets_for("svc_read")) is DemoSecrets
