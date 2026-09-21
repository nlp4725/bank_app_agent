"""Print the accessibility view of a page, the way the Discovery LLM would see it.

    python -m tools.a11y_dump http://localhost:5001/login
    python -m tools.a11y_dump https://www.saucedemo.com/     # a modern app, for contrast

Prints Playwright's ARIA snapshot (role + accessible name per line), then checks
which interactive controls could be found by role+name alone — rung 1 of a Target
ladder — and which would need a fallback.
"""

import re
import sys

from playwright.sync_api import sync_playwright

INTERACTIVE = ("button", "textbox", "link", "checkbox", "combobox", "radio", "menuitem", "searchbox")
LINE = re.compile(r'^(\s*)-\s+([a-z]+)(?:\s+"([^"]*)")?')


def dump(url: str, show_tree: bool = True):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(url, wait_until="domcontentloaded")
        page.wait_for_timeout(700)
        snapshot = page.locator("body").aria_snapshot()
        print(f"\n=== {url} ===")
        if show_tree:
            print(snapshot)

        print("--- interactive controls: can rung 1 (role + accessible name) find them? ---")
        found = missing = 0
        for line in snapshot.splitlines():
            m = LINE.match(line)
            if not m:
                continue
            _, role, name = m.groups()
            if role not in INTERACTIVE:
                continue
            if name:
                found += 1
                print(f'  {role:10s} "{name}"' + " " * max(0, 26 - len(name)) + "rung 1 works")
            else:
                missing += 1
                print(f"  {role:10s} (no accessible name)        NEEDS A FALLBACK RUNG")
        print(f"\n  {found} findable by role+name, {missing} need a fallback")
        browser.close()


if __name__ == "__main__":
    for url in sys.argv[1:] or ["http://localhost:5001/login"]:
        dump(url)
