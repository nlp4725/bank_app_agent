"""The demo app is the fixture: started once, reset before each test."""

import os
import socket
import subprocess
import sys
import time
import urllib.request

import pytest

from cua.artifact import Artifact, merged
from cua.profile import load_profile

from .fixtures import artifact_dict

VENDOR_APP = "demo-core-servicing"

PORT = 5099
ORIGIN = f"http://127.0.0.1:{PORT}"


def _up(url, timeout=15):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=1)
            return True
        except Exception:
            time.sleep(0.2)
    return False


def _serve(port: int, skin: str):
    """Start a demo app this test session owns, and stop it afterwards.

    It used to reuse whatever was already listening. That is silent corruption
    waiting to happen: the app keeps one global `store`, `/reset` wipes it, and the
    autouse fixture below resets it before every test — so a server left over from an
    earlier session, or a `tools.replay` running in another terminal, shares that
    state and clears a fire-once scenario mid-run. Member 88888's session then expires
    on every search instead of the first, and the run dies with `retries_exhausted`.

    The port is fixed rather than ephemeral because each Tenant Policy declares the
    instances automation may reach, and the harness's instance is one of them. So a
    port already in use is an error a person must clear, not something to work around.
    """
    origin = f"http://127.0.0.1:{port}"
    with socket.socket() as probe:
        if probe.connect_ex(("127.0.0.1", port)) == 0:
            pytest.exit(
                f"port {port} is already serving something. The test suite owns its "
                f"demo apps; a leftover one shares state with these tests and makes "
                f"the fire-once scenarios (54321, 77777, 88888) fail at random.\n"
                f"    pkill -f 'python -m fake_bank.app'",
                returncode=1)
    proc = subprocess.Popen([sys.executable, "-m", "fake_bank.app"],
                            env=dict(os.environ, PORT=str(port), SKIN=skin),
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        if not _up(f"{origin}/login"):
            proc.kill()
            pytest.exit(f"the demo app did not come up on {port}", returncode=1)
        yield origin
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


@pytest.fixture(scope="session")
def bank_app():
    yield from _serve(PORT, "bank1")


@pytest.fixture(scope="session")
def bank2_app():
    """The same product as a second institution: renamed controls, moved icon."""
    yield from _serve(PORT + 1, "bank2")


@pytest.fixture(autouse=True)
def reset_app(request):
    """Every test starts from the seed data, so runs are repeatable."""
    for name, origin in (("bank_app", ORIGIN), ("bank2_app", f"http://127.0.0.1:{PORT + 1}")):
        if name in request.fixturenames:
            urllib.request.urlopen(f"{origin}/reset", timeout=5).read()
    yield


@pytest.fixture
def artifact():
    """The hand-written reference Artifact, with its App Profile merged.

    One definition: four test modules used to carry a copy of this, and they drifted
    apart the moment the App Profile moved.
    """
    return merged(Artifact.model_validate(artifact_dict()), load_profile(VENDOR_APP))
