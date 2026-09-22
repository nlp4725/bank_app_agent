"""The demo app is the fixture: started once, reset before each test."""

import os
import socket
import subprocess
import sys
import time
import urllib.request

import pytest

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


@pytest.fixture(scope="session")
def bank_app():
    env = dict(os.environ, PORT=str(PORT), SKIN="bank1")
    with socket.socket() as s:
        already_running = s.connect_ex(("127.0.0.1", PORT)) == 0
    proc = None
    if not already_running:
        proc = subprocess.Popen(
            [sys.executable, "-m", "fake_bank.app"],
            env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        assert _up(f"{ORIGIN}/login"), "the demo app did not start"
    yield ORIGIN
    if proc:
        proc.terminate()


@pytest.fixture(scope="session")
def bank2_app():
    """The same product as a second institution: renamed controls, moved icon."""
    port = PORT + 1
    origin = f"http://127.0.0.1:{port}"
    env = dict(os.environ, PORT=str(port), SKIN="bank2")
    with socket.socket() as s:
        running = s.connect_ex(("127.0.0.1", port)) == 0
    proc = None
    if not running:
        proc = subprocess.Popen([sys.executable, "-m", "fake_bank.app"], env=env,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        assert _up(f"{origin}/login"), "the second institution did not start"
    yield origin
    if proc:
        proc.terminate()


@pytest.fixture(autouse=True)
def reset_app(request):
    """Every test starts from the seed data, so runs are repeatable."""
    for name, origin in (("bank_app", ORIGIN), ("bank2_app", f"http://127.0.0.1:{PORT + 1}")):
        if name in request.fixturenames:
            urllib.request.urlopen(f"{origin}/reset", timeout=5).read()
    yield
