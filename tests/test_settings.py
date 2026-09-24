"""Where the package finds its data, and which secrets it will resolve, are settings —
read from the environment once, changeable for a process, and honoured by every loader
at call time."""

import os
import shutil
from pathlib import Path

import pytest

from cua import settings as settings_module
from cua.governance.roles import UnknownRole, get_role, list_roles
from cua.secrets import DemoSecrets, EnvSecrets, MissingSecret, secrets_for
from cua.settings import DEFAULT_ROOT, Settings, configure, settings


@pytest.fixture
def restore_settings():
    before = (settings.root, settings.secrets_provider)
    yield
    configure(root=before[0], secrets_provider=before[1])


def test_the_default_root_is_the_repository_and_every_directory_hangs_off_it():
    s = Settings.from_env({})
    assert s.root == DEFAULT_ROOT
    assert s.roles_dir == DEFAULT_ROOT / "config" / "roles"
    assert s.artifacts_dir == DEFAULT_ROOT / "artifacts"
    assert s.overlays_dir == DEFAULT_ROOT / "overlays"


def test_cua_root_moves_every_directory(tmp_path):
    s = Settings.from_env({"CUA_ROOT": str(tmp_path)})
    assert s.root == tmp_path.resolve()
    assert s.policies_dir == tmp_path.resolve() / "config" / "policies"
    assert s.assets == tmp_path.resolve() / "artifacts" / "assets"


def test_demo_secrets_are_on_only_beside_the_demo_app(tmp_path):
    assert Settings.from_env({}).secrets_provider == "demo"          # this repo has fake_bank/
    assert Settings.from_env({"CUA_ROOT": str(tmp_path)}).secrets_provider == "env"
    assert Settings.from_env({"CUA_SECRETS": "env"}).secrets_provider == "env"
    with pytest.raises(ValueError):
        Settings.from_env({"CUA_SECRETS": "vault"})


def test_loaders_follow_a_new_root_with_no_cache_to_clear(tmp_path, restore_settings):
    """A second root with one more role: visible when configured, gone when not."""
    shutil.copytree(DEFAULT_ROOT / "config", tmp_path / "config")
    roles = tmp_path / "config" / "roles" / "demo-core-servicing.yaml"
    roles.write_text(roles.read_text() + "\nauditor:\n  pages: ['/reports']\n  actions: ['read']\n")

    assert "auditor" not in list_roles("demo-core-servicing")
    configure(root=tmp_path)
    assert settings_module.settings.roles_dir == tmp_path.resolve() / "config" / "roles"
    assert get_role("demo-core-servicing", "auditor")["pages"] == ["/reports"]
    configure(root=DEFAULT_ROOT)
    with pytest.raises(UnknownRole):
        get_role("demo-core-servicing", "auditor")


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
