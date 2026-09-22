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


@pytest.fixture(autouse=True)
def reset_app(request):
    """Every test starts from the seed data, so runs are repeatable."""
    if "bank_app" in request.fixturenames:
        urllib.request.urlopen(f"{ORIGIN}/reset", timeout=5).read()
    yield
